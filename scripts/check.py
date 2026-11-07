# /// script
# requires-python = ">=3.12"
# dependencies = ["jsonschema==4.25.1", "pyyaml==6.0.3"]
# ///
"""Static checks for the schemas, the examples and the conformance cases.

Usage (from the repository root):
  uv run scripts/check.py            # all checks; exit 1 on any finding
  uv run scripts/check.py --coverage # also print the rule coverage report

Checks:
  - every JSON Schema in schema/ and conformance/ against its meta-schema;
  - every examples/**/*.blokky.yaml against the plan schema;
  - every conformance case (conformance/README.md, CF-n): its structure
    (conformance/case.schema.json), matchers, cited rule IDs and spec
    sections, the feature list against the plan, the schema's verdict on
    the plan against the expected outcome, and suite-wide ports and locks.

Cases can't be run here; the runner that runs them belongs to an
implementation (CF-53). This script only checks what a case file claims.
"""

from __future__ import annotations

import base64
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent
PLAN_SCHEMA = ROOT / "schema" / "blokky.schema.json"
CASE_SCHEMA = ROOT / "conformance" / "case.schema.json"
CASES = ROOT / "conformance" / "cases"
CONFORMANCE_README = ROOT / "conformance" / "README.md"
SPEC = ROOT / "spec"

RULE_PREFIXES = ("SY", "EM", "RS", "ER", "VA", "CO", "SH", "CP", "RF")
RULE_DEF = re.compile(r"\*\*((?:" + "|".join(RULE_PREFIXES) + r")-\d+)\.\*\*")
MATCHERS = {
    "$absent",
    "$present",
    "$regex",
    "$one_of",
    "$min",
    "$max",
    "$unordered",
    "$contains",
    "$count",
    "$secret",
    "$delete",
}

findings: list[str] = []


def finding(where: Path | str, message: str) -> None:
    rel = where.relative_to(ROOT) if isinstance(where, Path) else where
    findings.append(f"{rel}: {message}")


# --- YAML loading -----------------------------------------------------------


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys (case files)."""


class PlanLoader(yaml.BaseLoader):
    """Every scalar is a string, as Blokky reads plans."""


def _no_duplicates(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", key_node.start_mark)
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates)


def load_plan(text: str) -> Any:
    return yaml.load(text, Loader=PlanLoader)


# --- spec data ----------------------------------------------------------------


def spec_rules() -> dict[str, str]:
    """Rule ID -> spec file name, from the bold `**XX-n.**` definitions."""
    rules: dict[str, str] = {}
    for path in sorted(SPEC.glob("*.md")):
        for rule in RULE_DEF.findall(path.read_text(encoding="utf-8")):
            if rule in rules:
                finding(path, f"rule {rule} is defined twice")
            rules[rule] = path.name
    return rules


def schema_rules() -> set[str]:
    """RF rules marked *(schema)*: the plan schema enforces them too."""
    text = (SPEC / "reference.md").read_text(encoding="utf-8")
    return set(re.findall(r"\*\*(RF-\d+)\.\*\*[^\n]*\*\(schema\)\*", text))


def readme_table(heading: str) -> list[list[str]]:
    """The first Markdown table after a line containing `heading`."""
    lines = CONFORMANCE_README.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if heading in line)
    rows, in_table = [], False
    for line in lines[start + 1 :]:
        if line.startswith("|"):
            in_table = True
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not set(cells[0]) <= set("-: "):
                rows.append(cells)
        elif in_table:
            break
    return rows[1:]


def feature_ids() -> set[str]:
    ids: set[str] = set()
    for _, cell in readme_table("**Features** let"):
        ids.update(re.findall(r"`([a-z0-9-]+)`", re.sub(r"\([^)]*\)", "", cell)))
    return ids


def exempt_rules() -> set[str]:
    return {row[0] for row in readme_table("**Rules without cases:**")}


def spec_sections(name: str) -> set[str]:
    path = SPEC / name
    if not path.exists():
        return set()
    return set(re.findall(r"^#+ (\d+(?:\.\d+)*)\.? ", path.read_text(encoding="utf-8"), re.MULTILINE))


# --- feature derivation (CF-11) -------------------------------------------------

KINDS = (
    "exec",
    "script",
    "do",
    "all",
    "any",
    "race",
    "if",
    "sleep",
    "log",
    "fail",
    "assert",
    "set",
    "return",
)
LEAF_OPTIONS = {
    "stdin": "stdin",
    "ok_exit": "ok-exit",
    "stderr": "stderr-merge",
    "encoding": "encoding",
    "capture_file": "capture-file",
}
MODIFIERS = {
    "when": "when",
    "timeout": "timeout",
    "lock": "lock",
    "tempdir": "tempdir",
    "cwd": "cwd",
    "env": "env",
    "export": "export",
    "container": "container",
    "services": "services",
    "finally": "finally",
    "ignore_errors": "ignore-errors",
    "attempt_timeout": "attempt-timeout",
    "while": "while",
    "until": "until",
    "backoff": "backoff",
    "jitter": "jitter",
    "collect": "collect",
    "carry": "carry",
    "index": "index",
}
SUBJECTS = {
    "var": "cond-var",
    "env": "cond-env",
    "path": "cond-path",
    "command": "cond-command",
    "host": "cond-host",
    "result": "cond-result",
    "probe": "cond-probe",
}
SHELLS = ("bash", "sh", "pwsh", "powershell", "zsh")
DISPLAY = ("name", "log", "fail", "message", "return")
# Ids the derivation can't decide on its own: a case may list them freely.
UNDERIVED = {"shell-bash", "shell-sh", "shell-pwsh", "shell-powershell", "shell-zsh"}


def _mapping(value: Any) -> dict:
    """The value if it is a mapping, else an empty one (malformed plans are expected)."""
    return value if isinstance(value, dict) else {}


def derive_features(plan: Any) -> set[str]:
    found: set[str] = set()
    if not isinstance(plan, dict):
        return found
    for key in ("inputs", "vars", "outputs", "defaults"):
        if key in plan:
            found.add(key)
    if isinstance(plan.get("defaults"), dict) and plan["defaults"].get("shell") in SHELLS:
        found.add("shell-" + plan["defaults"]["shell"])
    for value in _mapping(plan.get("vars")).values():
        _values(value, found, template=True)
    _node(plan, found)
    return found


def _values(value: Any, found: set[str], template: bool = False) -> None:
    if isinstance(value, dict):
        if "from_env" in value:
            found.add("from-env")
        if value.get("secret") == "true" and ("var" in value or "from_env" in value):
            found.add("secret-ref")
    elif isinstance(value, str) and template and re.search(r"(?<!\$)\$\{", value):
        found.add("interpolation")


def _condition(cond: Any, found: set[str]) -> None:
    if not isinstance(cond, dict):
        return
    for key in ("all", "any", "not"):
        if key in cond:
            found.add("cond-composite")
            for sub in cond[key] if key != "not" else [cond[key]]:
                _condition(sub, found)
    for key, feature in SUBJECTS.items():
        if key in cond:
            found.add(feature)
    if "json" in cond:
        found.add("cond-json")
    if any(op in cond for op in ("gt", "ge", "lt", "le")):
        found.add("cond-numeric")
    if isinstance(cond.get("path"), dict):
        _values(cond["path"], found)
    probe = cond.get("probe")
    if isinstance(probe, dict):
        _process(probe, found)


def _process(spec: dict, found: set[str]) -> None:
    """exec/script/shell/env of a node, probe or service."""
    if isinstance(spec.get("exec"), str):
        found.add("exec-string")
    if "script" in spec and spec.get("shell") in SHELLS:
        found.add("shell-" + spec["shell"])
    argv = spec.get("exec")
    for item in argv if isinstance(argv, list) else []:
        _values(item, found)
    for value in _mapping(spec.get("env")).values():
        _values(value, found)
    if "export" in spec:
        found.add("export")


def _node(node: Any, found: set[str]) -> None:
    if not isinstance(node, dict):
        return
    for kind in KINDS:
        # the string form of exec is exec-string (added in _process)
        if kind in node and (kind != "exec" or isinstance(node["exec"], list)):
            found.add(kind)
    _process(node, found)
    for key, feature in LEAF_OPTIONS.items():
        if key in node:
            found.add(feature)
    if "keep_descendants" in node:
        found.add("keep-descendants-detach" if node["keep_descendants"] == "detach" else "keep-descendants")
    if "capture" in node:
        found.add("capture-fields" if isinstance(node["capture"], dict) else "capture")
    if node.get("secret") == "true":
        found.add("secret")
    for key, feature in MODIFIERS.items():
        if key in node:
            found.add(feature)
    if "retry" in node:
        found.add("retry-condition" if isinstance(node["retry"], dict) else "retry")
        _condition(node["retry"], found)
    for key in ("when", "if", "assert", "while", "until"):
        _condition(node.get(key), found)
    loop = node.get("for")
    if isinstance(loop, dict):
        for source in ("each", "count", "glob", "items", "lines", "matrix"):
            if source in loop:
                found.add("for-" + source)
        if "concurrency" in loop:
            found.add("for-concurrency")
    for key in DISPLAY:
        _values(node.get(key), found, template=True)
    for value in _mapping(node.get("set")).values():
        _values(value, found, template=True)
    for key in ("cwd", "stdin"):
        _values(node.get(key), found)
    for service in node.get("services") or []:
        if isinstance(service, dict):
            _process(service, found)
            if isinstance(service.get("exec"), list):
                found.add("exec")
            _condition(service.get("ready"), found)
    for key in ("do", "all", "any", "race", "then", "else", "finally"):
        for child in node.get(key) or []:
            _node(child, found)


# --- checks -----------------------------------------------------------------------


def check_schemas() -> tuple[jsonschema.Draft202012Validator, jsonschema.Draft202012Validator]:
    validators = []
    for path in (PLAN_SCHEMA, CASE_SCHEMA):
        schema = json.loads(path.read_text(encoding="utf-8"))
        for error in jsonschema.Draft202012Validator(jsonschema.Draft202012Validator.META_SCHEMA).iter_errors(
            schema
        ):
            finding(path, f"not a valid JSON Schema: {error.message}")
        validators.append(jsonschema.Draft202012Validator(schema))
    return validators[0], validators[1]


def check_examples(plan_validator: jsonschema.Draft202012Validator) -> int:
    files = sorted((ROOT / "examples").rglob("*.blokky.yaml"))
    for path in files:
        try:
            plan = load_plan(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            finding(path, f"not valid YAML: {error}")
            continue
        if (error := jsonschema.exceptions.best_match(plan_validator.iter_errors(plan))) is not None:
            finding(path, f"plan schema: {error.json_path}: {error.message[:200]}")
    return len(files)


def check_matchers(where: Path, value: Any, path: str) -> None:
    if isinstance(value, dict):
        dollar = [k for k in value if isinstance(k, str) and k.startswith("$")]
        if dollar:
            unknown = set(dollar) - MATCHERS
            if unknown:
                finding(where, f"{path}: unknown matcher {sorted(unknown)}")
            if len(value) > 1 and set(value) - {"$min", "$max"}:
                finding(where, f"{path}: a matcher is a single-key mapping (only $min/$max pair up)")
        for key, sub in value.items():
            check_matchers(where, sub, f"{path}.{key}")
    elif isinstance(value, list):
        for i, sub in enumerate(value):
            check_matchers(where, sub, f"{path}[{i}]")


def check_positions(where: Path, text: str, plan_errors: list) -> None:
    """Each asserted line exists, and each asserted column lands on a character that isn't
    whitespace (SY-1: lines end at LF, CRLF or a lone CR; columns are code points; a BOM
    isn't counted)."""
    lines = re.split(r"\r\n|\r|\n", text.removeprefix("\ufeff"))
    for error in plan_errors:
        line, column = error.get("line"), error.get("column")
        if not isinstance(line, int):
            continue
        if line > len(lines):
            finding(where, f"{error['code']} at line {line}: the plan has {len(lines)} lines")
        elif error["code"] in ("BK_PLAN_CHARACTER", "BK_PLAN_ENCODING"):
            # these point at the offending character, which may end the line (a lone CR)
            if isinstance(column, int) and column > len(lines[line - 1]) + 1:
                finding(where, f"{error['code']} at {line}:{column} is past the end of the line")
        elif isinstance(column, int) and not (
            column <= len(lines[line - 1]) and not lines[line - 1][column - 1].isspace()
        ):
            finding(where, f"{error['code']} at {line}:{column} points at no token (SY-1, CF-15)")


def plan_of(case: dict) -> tuple[str | None, str | None]:
    """The plan text, or an error why it can't be read."""
    if "plan" in case:
        return case["plan"], None
    try:
        return base64.b64decode(case["plan_base64"], validate=True).decode("utf-8"), None
    except (ValueError, UnicodeDecodeError):
        return None, "plan_base64 isn't UTF-8 text (fine for encoding cases)"


def collect_lock_names(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        lock = node.get("lock")
        if isinstance(lock, str):
            out.append(lock)
        elif isinstance(lock, dict) and "name" in lock:
            out.append(lock["name"])
        for value in node.values():
            collect_lock_names(value, out)
    elif isinstance(node, list):
        for value in node:
            collect_lock_names(value, out)


def collect_ports(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        if "port" in node and isinstance(node["port"], str):
            out.append(node["port"])
        for value in node.values():
            collect_ports(value, out)
    elif isinstance(node, list):
        for value in node:
            collect_ports(value, out)


def check_case(
    path: Path,
    case_validator: jsonschema.Draft202012Validator,
    plan_validator: jsonschema.Draft202012Validator,
    rules: dict[str, str],
    schema_enforced: set[str],
    features: set[str],
    ports: dict[int, list[str]],
) -> list[str]:
    """Check one case; return the rule IDs it cites."""
    case_id = path.relative_to(CASES).with_suffix("").as_posix()
    if not re.fullmatch(r"[a-z0-9-]+(/[a-z0-9-]+)+", case_id):
        finding(path, "case ids are lowercase kebab-case paths below an area directory (CF-6, CF-7)")
    try:
        case = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except yaml.YAMLError as error:
        finding(path, f"not valid YAML: {error}")
        return []
    errors = list(case_validator.iter_errors(case))
    for error in errors:
        finding(path, f"case schema: {error.json_path}: {error.message[:200]}")
    if errors or not isinstance(case, dict):
        return []

    cited = list(case.get("rules", []))
    for rule in cited:
        if rule not in rules:
            finding(path, f"cites {rule}, which no spec file defines")
    for ref in case.get("spec", []):
        name, _, section = ref.partition("§")
        if section not in spec_sections(name):
            finding(path, f"spec reference {ref} names no section")
    check_matchers(path, case["expect"], "expect")
    for key, override in (case.get("platforms") or {}).items():
        if "expect" in override:
            check_matchers(path, override["expect"], f"platforms.{key}.expect")

    expect = case["expect"]
    plan_errors = expect.get("plan_errors", [])
    for error in plan_errors:
        if error["code"] == "BK_PLAN_INVALID" and "rule" not in (error.get("detail") or {}):
            finding(path, "every BK_PLAN_INVALID asserts detail.rule (CF-24)")
        rule = (error.get("detail") or {}).get("rule")
        if isinstance(rule, str) and rule not in rules:
            finding(path, f"detail.rule {rule} names no rule")

    for feature in case["features"]:
        if feature not in features:
            finding(path, f"unknown feature id {feature!r} (conformance/README.md §3.2)")

    text, problem = plan_of(case)
    if text is not None:
        check_positions(path, text, plan_errors)
    if text is None:
        if not plan_errors:
            finding(path, problem or "no plan")
        return cited
    try:
        plan = load_plan(text)
    except yaml.YAMLError:
        plan = None
        if not plan_errors:
            finding(path, "the plan isn't valid YAML, but the case expects no plan error")

    if plan is not None:
        schema_ok = plan_validator.is_valid(plan)
        must_reject = [
            e
            for e in plan_errors
            if e["code"] == "BK_PLAN_UNKNOWN_KEY"
            or (e["code"] == "BK_PLAN_INVALID" and (e.get("detail") or {}).get("rule") in schema_enforced)
        ]
        if not plan_errors and not schema_ok:
            first = jsonschema.exceptions.best_match(plan_validator.iter_errors(plan))
            finding(
                path,
                f"the plan should be valid, but the schema rejects it: {first.json_path}: {first.message[:160]}",
            )
        if must_reject and schema_ok:
            finding(path, "the case expects an error the schema enforces, but the schema accepts the plan")

        derived = derive_features(plan)
        derived |= {
            a
            for action in case.get("actions", [])
            for a in ("external-stop", "kill")
            if action.get(a.replace("external-", "")) is True
        }
        declared = set(case["features"])
        if not isinstance(plan, dict):  # a root that isn't a mapping uses no derivable feature
            derived = declared
        if missing := derived - declared:
            finding(path, f"features: the plan uses {sorted(missing)}, which the case doesn't list (CF-11)")
        if extra := declared - derived - UNDERIVED:
            finding(path, f"features: the case lists {sorted(extra)}, which the plan doesn't use (CF-11)")

        locks: list[str] = []
        collect_lock_names(plan, locks)
        for name in locks:
            if not name.startswith("conf-" + path.stem):
                finding(path, f"lock {name!r} doesn't start with conf-{path.stem} (CF-14)")
        used: list[str] = []
        collect_ports(plan, used)
        listed = {str(p) for p in (case.get("requires") or {}).get("ports", [])}
        if unlisted := set(used) - listed:
            finding(path, f"ports {sorted(unlisted)} aren't listed in requires.ports (CF-14)")
    for port in (case.get("requires") or {}).get("ports", []):
        ports[int(port)].append(case_id)
    return cited


def coverage_report(rules: dict[str, str], cited: dict[str, list[str]], exempt: set[str]) -> None:
    by_file: dict[str, list[str]] = defaultdict(list)
    for rule, name in rules.items():
        by_file[name].append(rule)
    total = covered = 0
    print("\nRule coverage (CF-52): cited by a case or exempt")
    for name in sorted(by_file):
        ids = sorted(by_file[name], key=lambda r: int(r.split("-")[1]))
        done = [r for r in ids if r in cited or r in exempt]
        total, covered = total + len(ids), covered + len(done)
        missing = [r for r in ids if r not in done]
        print(f"  {name:22} {len(done):3}/{len(ids):<3}", end="")
        print(
            f"  uncovered: {', '.join(missing)}"
            if missing and len(missing) <= 12
            else f"  uncovered: {len(missing)}"
            if missing
            else ""
        )
    print(f"  {'total':22} {covered:3}/{total:<3} ({100 * covered // max(total, 1)}%)")


def main() -> int:
    report = "--coverage" in sys.argv[1:]
    plan_validator, case_validator = check_schemas()
    examples = check_examples(plan_validator)

    rules = spec_rules()
    schema_enforced = schema_rules()
    features = feature_ids()
    exempt = exempt_rules()
    for rule in exempt - set(rules):
        finding(CONFORMANCE_README, f"exempt rule {rule} isn't defined")

    cited: dict[str, list[str]] = defaultdict(list)
    ports: dict[int, list[str]] = defaultdict(list)
    case_files = sorted(CASES.rglob("*.yaml"))
    for path in sorted(CASES.rglob("*")):
        if path.is_file() and path.suffix != ".yaml" and path.name != ".gitkeep":
            finding(path, "case files end in .yaml (CF-7)")
    for path in case_files:
        for rule in check_case(path, case_validator, plan_validator, rules, schema_enforced, features, ports):
            cited[rule].append(path.relative_to(CASES).with_suffix("").as_posix())
    for port, users in ports.items():
        if not 47000 <= port <= 47999:
            finding(CASES, f"port {port} is outside 47000-47999 (CF-14): {users}")
        if len(users) > 1:
            finding(CASES, f"port {port} is used by more than one case (CF-14): {users}")

    for line in findings:
        print(line)
    print(f"{examples} examples, {len(case_files)} cases, {len(findings)} findings")
    if report:
        coverage_report(rules, cited, exempt)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
