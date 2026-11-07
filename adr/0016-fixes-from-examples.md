# 0016: Fixes found while writing the example suite

- Status: accepted
- Date: 2026-11-06
- Questions: none from the brief; raised by the example and conformance work (T-0031)

## Context and problem statement

Four agents wrote the basic examples, the end-to-end scenarios, the conformance case format and the overview in parallel. Writing realistic plans and test cases against the spec surfaced a bug in a spec example, rules that contradicted each other or plain shell syntax, and gaps. Three needed a decision and were asked as multiple choices with examples, on 2026-11-06; the rest are corrections or clarifications.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| The error of a group whose child failed | **the child's error itself (no wrapper)**; a `BK_CHILD_FAILED` wrapper with the child's error as cause |
| A child of an ordered `any` skipped by `when` | **doesn't take part: `any` moves on to the next child**; counts as success |
| Testing whether a program is installed | **a new `command:` condition subject**; a probe of a missing program counts as false; document an `sh` pattern |

## Decision outcome

All three answers follow the recommendation.

### Decisions

- **A failed group carries its child's error** (EM-66): same code, `detail` and `node`, at any nesting depth, so `retry:` conditions and `result: error` on a group see the real cause. With several failures (`do` with `fail_fast: false`, `all`) the first in plan order is the group's error and the others are attached; aggregates (`BK_ANY_ALL_FAILED`) keep their own code.
- **`any` and `when`** (EM-45, reference §2.5): a skipped child doesn't take part, as in `race`; an ordered `any` tries the next child.
- **`command:` subject** (CO-45, CO-46): `{ command: NAME, exists: true }` is true if `NAME` resolves like an `exec` argv[0]; nothing is started. Probes of missing programs stay condition errors.

### Corrections

- **`race` example** (reference §2.6; also the example in ADR 0014): the watchdog wrapped `until: { probe }` around a `fail`, but `until` checks its condition only after a successful iteration, so the probe never ran. The example now polls with a leaf (`ok_exit` for "no match yet") and fails after it.
- **`${` in `script` text** (syntax §7.1, SH-14): the rule "a `${` in a literal field is a plan error" also caught shell syntax such as `${VAR:-x}` and PowerShell `${env:X}`. Script text is exempt; implementations SHOULD warn when `${NAME}` in a POSIX script names a plan variable the node doesn't export.

### Clarifications

- **Empty `items`/`lines` sources** run zero iterations and succeed; only `glob` needs `allow_empty`.
- **`collect`** gathers a capture bound in the iteration by the `for` node itself (when it is a leaf) or by a node in its body; iterations that failed, were skipped or didn't bind it give `null`.
- **Container `cwd`:** an absolute `cwd` under `container` that isn't under a mount is a container path and is checked in the container, not on the host.
- **`env_pass`:** a name that isn't set is not passed, without an error.
- **Path ids:** the root is `/`; a node in a body field adds `/<field>/<index>` (`/then/1`, `/finally/0`); nodes in loop bodies keep their plan id.
- **Rule IDs:** reference §8's rules are now `RF-1` to `RF-28` (used by conformance cases and `detail.rule`).
- **Plan error positions** point at the offending key, or at its value when the value is what is wrong.
- The glossary's kind list includes `set`.

### Left for the review

- A `while` body can't see the previous iteration's captures, so cursor pagination can't be written (VA-33).
- EM-22 stops every descendant at run end, so a plan can't start a long-lived daemon (for example Docker Desktop on Windows); `keep_descendants` only applies until the run ends.
- `syntax.md` has no rule IDs yet.

### Consequences

- Good: the examples and conformance format rest on rules without known contradictions.
- Good: "is this tool installed?" no longer needs a shell.
- Neutral: error chains are flatter; where a failure happened is in the error's `node`.

## More information

- Applied in: `spec/execution-model.md` (EM-43, EM-45, EM-52, EM-66), `spec/reference.md` (§1, §2.5, §2.6, §4.6, §5.7, §8), `spec/conditions.md` (§2.4), `spec/syntax.md` (§1, §7.1, per-field table), `spec/shells.md` (SH-14), `spec/containers.md` (CP-16), `spec/glossary.md`, `schema/blokky.schema.json`.
- Tracker: T-0057; findings F-0008 to F-0010.
