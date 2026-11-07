# 0023: Gaps found by the wave C conformance cases

- Status: accepted
- Date: 2026-11-07
- Questions: none from the brief; raised while writing and checking the wave C condition and shell cases (tracker T-0063, F-0019; [review notes](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/review/conformance-wave-c.md))

## Context and problem statement

Three agents wrote the wave C cases (condition subjects and operators, composites and probes, shells), and three more read them against the spec. Wrong cases were fixed; most had columns counted before the plan's indentation was stripped. The remaining gaps leave glob matching, executable resolution, condition errors and several shell details undetermined, and some statements had no rule ID. The maintainer decided G-1 and G-2 and accepted the batch K-1 to K-7 on 2026-11-07.

## Considered options

| Item | Options (chosen in bold) |
|---|---|
| G-1 glob semantics | **files and directories match; `*`/`**` skip dot-entries unless the segment starts with `.`; links matched, never followed into; a `..` segment is a plan error**; the same with files only |
| G-2 resolution through symbolic links | **not followed: `program` is the path found on `PATH`, and the process starts under it**; the canonical path, with testkit aliases copied or hard-linked |
| K-1 to K-7 | **accepted as a batch** |

## Decision outcome

- **G-1.** A glob matches files and directories (SY-99). `*` and `**` never enter or match dot-entries unless the pattern segment starts with `.` (SY-100). A symbolic link is matched as an entry but never followed into (SY-101). A literal `..` segment is a plan error, `BK_PLAN_VALUE` (SY-102). reference.md §5.7 points at these rules.
- **G-2.** Resolution doesn't follow symbolic links: `program` is the path found on `PATH`, and the process starts under that path, so a symlinked tool keeps its name (SH-29, results.md `program`).
- **K-1 Rule IDs and codes.**
  - SY-91 is reported over CO-4, SY-53 over CO-8 (SY-3, errors.md §4).
  - A probe shape violation is `BK_PLAN_INVALID` with rule CO-26; the schema allows a probe's `shell` only with `script`.
  - A node used as a condition is `BK_PLAN_INVALID` at the kind key.
  - `ignore_case` also works on `not_equals`, `not_in`, `not_contains` and `not_matches` (CO-12).
  - A missing subject or operator is CO-4, not CO-1.
  - A `{ var: X }` in a literal field is RF-9 alone.
  - New rule IDs: the operator table's valid subjects (CO-47), the subject table (CO-48), the meaning of `exists`, `is_file` and `is_dir` (CO-49), and `not_*` negating its operator (CO-50).
- **K-2 Positions.** A missing operator is reported at the subject key; an error in a block scalar at the first character of its first content line (SY-1).
- **K-3 Condition errors.**
  - Each CO-38 bullet names its `detail.reason`; an unset environment variable is `undefined_variable`.
  - CO-40 covers any condition error caused by the `result:` value.
  - `defined`/`not_defined` on invalid JSON is a condition error (`json_invalid`); only a missing path counts as undefined (CO-22).
  - A loop or retry ended by a condition error has `ended_by: failure`.
- **K-4 Probes.**
  - A probe's `invocation` follows the leaf rules, and the `probes` list is in execution order (results.md).
  - A probe that hits its timeout gets the grace period, like a leaf (CO-28, EM-26).
  - A bare probe's stdout isn't decoded or checked for its encoding (CO-33).
  - The first readiness check happens right after the service process starts; later ones come 250ms after the previous check ends (reference.md §4.9).
- **K-5 `host:`.** A branch decided statically by `host:` is `pruned`, not `not_taken` (CO-7 wins over E-1 of [ADR 0022](0022-wave-b-gaps.md)).
- **K-6 Shells.**
  - A literal argv[0] ending in `.bat` or `.cmd` (case-insensitive) is `BK_PLAN_VALUE` with rule SH-10; SH-27's extension trial applies to bare names only.
  - A backslash-escaped character is always literal, `\$` and a backslash-escaped backtick included; a trailing lone backslash is an SH-7 error (SH-5, SH-7).
  - Windows quoting follows `ProcessStartInfo.ArgumentList` (the Microsoft C runtime rules), normatively (SH-9).
  - In a `script` leaf's `invocation`, element 0 is the resolved shell path.
  - The `param(` check applies only to a shell named `pwsh` or `powershell` by `shell:` or `defaults.shell` (SH-17).
  - The Windows prologue is `$ErrorActionPreference = 'Stop'; [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false);`, followed by a space (SH-34).
- **K-7 Conformance format.**
  - Conformance runs use no implementation configuration, such as shell paths (CF-57).
  - The testkit gets `chmod MODE PATH` (TK-23, Unix), so `path_access` errors are testable.
  - CO-10, CO-15, CO-32, CO-37, SH-8, SH-19, SH-20 and SH-30 are exempt, and SH-11's file-mode part.

### Consequences

- Good: glob items, `program` and condition error reasons are fully determined, so the wave C cases can assert them on every OS.
- Good: symlinked tools and testkit aliases keep their names, as with `bash -c`.
- Neutral: a glob with a `..` segment is rejected before the run, and testkits implement one more command.

## More information

- Applied in: `spec/conditions.md`, `spec/syntax.md`, `spec/reference.md`, `spec/shells.md`, `spec/errors.md`, `spec/results.md`, `spec/execution-model.md`, `schema/blokky.schema.json`, `conformance/README.md`, `conformance/testkit-interface.md`.
- Tracker: T-0063; finding F-0019.
