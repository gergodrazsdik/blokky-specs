# 0019: Review corrections

- Status: accepted
- Date: 2026-11-07
- Questions: none from the brief; raised by the agent council's review of `1.0.0-draft.3` (items C-1 to C-8) and by the maintainer (F-0012)

## Context and problem statement

Besides the decisions in ADR 0017 and ADR 0018, the council found corrections whose answer was clear: schema errors at the wrong key, documentation that steers agents wrong, security wording, unclear execution rules, example bugs, conformance-format gaps and mechanical errors ([council report](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/review/council-draft.3.md) §3). The maintainer accepted them as a batch on 2026-11-07, adjusted for the other decisions, and answered three open points.

## Considered options

| Item | Options (chosen in bold) |
|---|---|
| The batch C-1 to C-7 | **accept, adjusted for ADR 0017 and 0018**; review groups first |
| `exec` string form | **canonical for a static argv with no quoting and no variables**; array form only |
| Warning when running as root (CP-32) | SHOULD warn; **no warning** |
| Lock scope across users | **per user, stated explicitly**; machine-wide |
| C-8 `command:` | **requires an executable file**; existence only |

## Decision outcome

- **C-1 Schema.**
  - Every key a node may carry is listed in the node's own schema object with `additionalProperties: false`, so a bad value is reported at its own key (`retry: 3` no longer blames `exec`).
  - The rules the schema can express moved into it: the validity matrix and sibling table (RF-3), RF-4, RF-5, RF-12, RF-18, RF-25, RF-28, RF-31, and two new rules, RF-32 (companion fields with their owner) and RF-33 (no `ignore_errors` on the root).
  - reference.md §8 becomes "Rules beyond the schema" and marks the rules the schema also enforces.
  - Contradictory cells are fixed: `race` takes `concurrency` inside `for:`; §5.2 gets a `for` column.
  - Exit codes get their own range, 0 to 4 294 967 295 (SY-96).
- **C-2 Documentation agents rely on.**
  - The `${X}` fix-it names the `set` template first.
  - `retry: 3` becomes `max: 4`, because `max` counts attempts.
  - The overview lists `command`, `port` and `output`, and has an idioms table.
  - Errors inside loops carry `iteration` and `item`.
  - syntax.md has a canonical-forms table (SY-97), with the `exec` string form canonical for a static argv.
- **C-3 Security wording.**
  - A template result used as code is string interpolation into code (VA-57, shells §6, reference §9), which corrects ADR 0015's "can't inject shell syntax".
  - A secret in an `exec` element is on the command line, and implementations SHOULD warn.
  - Values derived from a secret are secret (VA-50).
  - Allowing `blokky run` without the approval mechanism allows everything, like allowing `bash`.
  - Run-owned files are created new and removed without following links (EM-69).
  - Rendered text is display-sanitized (SY-98).
  - The list of execution-influencing variables is illustrative, and grows.
  - `stdin` is the fourth route into a process.
  - Constrain inputs with `matches` and pass `--` against option-like values.
- **C-4 Execution clarifications.**
  - A `finally` list's deadline is its own `finally_timeout` (EM-25).
  - errors.md has the complete "Retried" column.
  - `ignore_errors` covers a node's own timeout, and isn't valid on the root.
  - A failed attempt's captures are best effort, for `retry` conditions only.
  - RS-6 keeps `when` probes, and a `pruned` skip reason is added.
  - CP-1 notes the CP-14 exception.
  - Normative keywords are capitalized.
  - Windows graceful stop: a hidden console, or `graceful: none`.
  - The PowerShell prologue rejects attributes before `param`; execution-policy blocks are `BK_SPAWN_FAILED`.
  - Readiness polls at most 250ms apart; the reap timeout is implementation-defined (at least 1s); the jitter source MAY be seedable; lock waiters are served in no particular order.
  - Locks are per user, root included.
- **C-5 Examples.**
  - when-guard checks `defined` first.
  - dotnet-build-test's header matches what it does.
  - changed-files-lint uses `command:`.
  - retry-backoff explains `max`.
- **C-6 Conformance format.**
  - A passthrough environment per requirement.
  - A `kill` action and `after_run` checks (CF-64).
  - Rules that can't be tested through the result are listed with a reason, and execution-model §10 points to that list.
  - Per-OS clock and timing defaults.
  - The drain bound and lock polling join the test clock.
- **C-7 Mechanical fixes.**
  - The `vars` synonym, the VA-56 anchor and ADR 0010's EM-54 note.
  - The SH-31 gap note.
  - Glossary "Plan", "Modifier" and "Group".
  - One `ended_by` value set.
  - `bindings` for loops and `tempdir`.
  - `assert` in EM-8.
  - An `output_encoding` condition-error reason.
  - CP-7 and SH-20 no longer promise future spec text.
- **C-8:** `command:` is true only for a file that exists and that the current user may execute (CO-45).
- **Running as root:** CP-32's warning is dropped with `become` (ADR 0017). `sudo blokky run` is like `sudo bash plan.sh`.

### Consequences

- Good: an agent with only the schema catches most invalid plans, at the right key.
- Good: the documentation agents read first points to the canonical form for each intent.
- Neutral: the schema is larger, because the root repeats the node's key list.
- Deferred: minimum shell versions (IMP-15) wait for the shell spikes.

## More information

- Applied in: `schema/blokky.schema.json`, every file in `spec/`, `conformance/README.md`, `examples/`, `adr/0010-variables-details.md` (note).
- Tracker: T-0051; finding F-0012.
