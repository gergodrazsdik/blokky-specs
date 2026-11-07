# 0002: Language core (open-question batch 1)

- Status: accepted; the regex dialect is superseded by [ADR 0018](0018-review-semantics.md)
- Date: 2026-11-04
- Questions: Q1, Q2, Q3, Q12, Q13, Q-m, Q-n, Q-s

## Context and problem statement

The [specification-phase brief](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/design/brief.md) §4 lists questions that must be answered before the language spec draft is written. This ADR records the maintainer's answers to batch 1, the language core: modifier order, JSON paths and `collect`, condition semantics, `name` uniqueness, the plan version field, and three scoping and error rules. It refines [ADR 0001](0001-language-baseline.md).

Each question was asked as a multiple choice with a recommendation, on 2026-11-04. The options considered are listed per decision below; the chosen one is marked.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| Q1 modifier order | **brief order as written**; `finally` outside `services`; other order |
| Q2a JSON path subset | **minimal jq-like**; minimal plus negative indices; RFC 9535 JSONPath subset |
| Q2b `collect` | **`later`, brief syntax**; `v0.1`, brief syntax; `later`, other syntax |
| Q3 subject/operator tables | **as written**; add `starts_with`/`ends_with`; other changes |
| Q3a `matches` | **unanchored search over the whole value**; any line matches; implicit full match |
| Q3b trimming | **all trailing CR/LF**; one trailing newline; all trailing whitespace |
| Q3c number grammar | **plain decimal**; integers only; lenient float |
| Q3d probe defaults | **30s / 64 KiB**; 10s / 16 KiB; 60s / 1 MiB |
| Q12 `name` uniqueness | **not required, lint duplicates**; not required, no lint; unique per plan |
| Q13 `blokky:` | **required, `MAJOR.MINOR`**; optional, `MAJOR.MINOR`; required, full semver |
| Q-m `empty` on undefined | **condition error**; undefined counts as empty |
| Q-n condition error in `assert` | **built-in condition-error code**; the assertion's user code |
| Q-s captures in `finally` | no captures; **finally-local**; published on success |

## Decision outcome

All answers follow the recommendation except Q-s, where the maintainer chose finally-local captures over forbidding them.

### Q1: modifier order

Confirmed as written. Outermost to innermost (normative):

`when` → `timeout` → `lock` → `tempdir` → `cwd` → `env` → `container`/`become` → `services` → `finally` → repetition (`retry` | `while` | `until` | `for`) → `attempt_timeout` → node kind (incl. `capture`).

- A node skipped by `when` takes no lock, creates no tempdir, starts no container or service and runs no `finally`.
- `timeout` covers lock wait, tempdir creation, container start, service startup, the body and all repetition.
- `finally` runs once per node, not per iteration. It runs inside the node's tempdir, cwd, env, container and services, so cleanup can use them, and under its own `finally_timeout`, even after `timeout` fired.

### Q2: JSON paths and `collect`

**JSON path subset** for `json:` in conditions and for multi-field `capture`, jq-like:

- `.` is the whole value;
- `.name` selects an object member whose key matches `^[A-Za-z_][A-Za-z0-9_]*$`;
- `.["any key"]` (double-quoted, JSON string escapes) selects any other member; after the first segment the leading `.` is optional for brackets (`.a["b-c"]`, `.[0]`);
- `[N]` selects an array element by non-negative decimal index.

Examples: `.number`, `.head.ref`, `.[0].databaseId`, `.labels[1].name`, `.["weird-key"].x`. Wildcards (`.[]`), negative indices, slices, recursive descent, filters and pipes are rejected at parse time. A path that doesn't resolve at runtime is a condition error (or, for `capture`, the node's distinct missing-path failure), as the baseline says.

**`collect`** is `later`, with the brief's syntax: `collect: { CAPTURE: LISTVAR }` on a `for` node, list ordered by item index, `null` for failed or skipped iterations. The keyword and value shape are reserved in v0.1. In v0.1, `for` iterations can't pass values out of the loop.

### Q3: conditions

**Tables confirmed as written** (brief §3.1): subjects `var`, `env`, `path`, `host`, `result`, `probe` (and `port`/`output` for `services`, later); operators `equals`/`not_equals`, `in`/`not_in`, `contains`/`not_contains`, `matches`/`not_matches`, `empty`/`not_empty`, `defined`/`not_defined`, `exists`/`not_exists`, `is_file`, `is_dir`, `open`, `gt`/`ge`/`lt`/`le`; options `json:` and `ignore_case:`; composites `all`/`any`/`not`. No `starts_with`/`ends_with`: prefix and suffix tests use `matches`.

**`matches`/`not_matches`:** an unanchored search over the whole value (true if the pattern matches anywhere), with `RegexOptions.NonBacktracking` and the invariant culture. There is no implicit multiline mode: `^` and `$` anchor at the start and end of the whole value. Inline options (`(?m)`, `(?s)`, `(?i)`) are allowed; `ignore_case: true` is equivalent to `(?i)`. Plan-input `matches:` constraints use the same semantics.

**Trimming:** when process output becomes a value (`capture`, `result: stdout|stderr`, probe stdout), **every trailing `\n` and `\r` is removed**, like bash `$(…)`. Spaces and tabs are kept. Nothing else is trimmed: plan variables, env values and input values are compared as they are. This replaces the brief's per-operator "trailing `\r?\n` trimmed" note for `equals`; every operator sees the same text.

**Number grammar** for `gt`/`ge`/`lt`/`le`: the whole value must match `^-?[0-9]+(\.[0-9]+)?$` and is compared as an exact decimal (invariant culture). Leading zeros are allowed. A leading `+`, exponents, hex, digit-group separators, surrounding whitespace, `.5`, `5.`, `NaN` and `Infinity` are condition errors. The operand in the plan follows the same grammar (a plan error otherwise).

**Probe defaults:** `probe_timeout` 30s and a probe stdout limit of 64 KiB. Both are free config keys; a probe's own `timeout:` overrides the timeout. Output over the limit is a condition error.

### Q12: `name` uniqueness

`name` values need not be unique. Path ids (`/do/2/all/0`) identify nodes in the report, events, errors and file names. A low-severity lint rule flags identical static `name` templates among siblings.

### Q13: the `blokky:` field

`blokky:` is **required** and holds the spec version as `MAJOR.MINOR` (`blokky: 0.1`), matching `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`. Spec patch releases never change the language, so plans don't name them. A missing field is a parse error; a version the binary doesn't support is a parse error that lists the supported versions.

### Q-m: `empty`/`not_empty` on an undefined variable

A condition error, like every other operator except `defined`/`not_defined`. "Undefined or blank" is written `{ any: [ { var: X, not_defined: true }, { var: X, empty: true } ] }`. Inputs are always defined, so this affects captures and loop variables only.

### Q-n: condition error inside `assert`

The node fails with the built-in condition-error code (named in `spec/errors.md`), not with the assertion's user `code`. The assertion's `message` and `code` are attached to the error as context. "The check couldn't be evaluated" stays distinct from "the check was false", so `retry` conditions on the user code don't fire on broken checks.

### Q-s: captures in `finally`

`capture`/`capture_file` are allowed on nodes under `finally`, and the bindings are **finally-local**:

- visible to later nodes in the same `finally` list (and their descendants), by the usual sequence rules;
- never published outside the `finally` list: not to the node, its parent or `outputs:` (referencing one there is a static error);
- the shadowing rule applies, so a `finally` capture can't reuse a name the body or an enclosing scope binds.

### Consequences

- Good: the draft spec can fix condition semantics, the JSON path grammar and the version field without placeholders.
- Good: condition errors are uniformly distinct from false results (Q-m, Q-n).
- Neutral: in .NET, `$` also matches before a final newline. Trimming removes trailing newlines from process output, so this only shows on plan variables that end in a newline; `syntax.md` documents `\z` for a strict end.
- Neutral: `collect` stays `later`, so v0.1 `for` loops can't return values; plans that need a result per item use separate nodes or files.
- Bad: finally-local captures add a scope rule to `variables.md` and need conformance cases (visibility to later `finally` siblings, the static error for references outside, shadowing).

## More information

- Brief: §3.1 (modifiers, conditions, variables), §3.2 (versioning), §4 (questions).
- Tracker: T-0008; the answers are linked from the [open-questions table](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/plan/TRACKER.md#open-questions).
- Spec files that apply these answers: `spec/execution-model.md` (Q1), `spec/variables.md` (Q2, Q-s), `spec/conditions.md` (Q3, Q-m, Q-n), `spec/syntax.md` (Q12, Q13), `spec/errors.md` (condition-error code).
