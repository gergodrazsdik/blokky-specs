# 0009: Status propagation and joins (draft round 3)

- Status: accepted
- Date: 2026-11-05
- Questions: none from the brief's §4 list; the brief's §3.8 says status propagation "must be specified" (D15), and blokky-specs ADR 0003 left the reap timeout open. Raised while drafting `spec/execution-model.md` (T-0017).

## Context and problem statement

The brief lists five status-propagation cases that the execution model must settle, and ADR 0003 (Q-k) mentioned a "fixed reap timeout" after the grace period without a value. They were asked as multiple choices with a recommendation, on 2026-11-05.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| A group whose children were all skipped | **succeeded**; skipped |
| An ignored failure in `any` | **not a success: `any` moves on**; it wins |
| Parent status for a timed-out or cancelled child | **own cause only; the parent is `failed` with the child's error**; propagate `timed_out` |
| Exit code when the root `when` is false | **exit 0, root `skipped`, run `succeeded`**; a distinct exit code |
| `ignore_errors` and a condition error in `when` | **applies**; doesn't apply |
| Reap timeout | 2s; **5s**; 1s |

## Decision outcome

All answers follow the recommendation except the reap timeout, where the maintainer chose 5s over 2s.

- **All children skipped:** a `do`, `all` or `any` whose children were all skipped by `when` is `succeeded`, and its `finally` runs. `any` succeeds if a child succeeded or none failed, and fails if none succeeded and at least one failed.
- **Ignored failures in `any`:** a child that failed with `ignore_errors: true` doesn't fail its parent, but it isn't a success either. `any` tries the next alternative; if none succeeds, the ignored failures are among its causes.
- **Own cause only:** a node is `timed_out` only if its own `timeout` or `attempt_timeout` fired, and `cancelled` only if it was stopped from outside. A parent whose child timed out or was cancelled is `failed`, with the child's error as a cause.
- **Root `when` false:** exit 0; the root node is `skipped` and the run status is `succeeded`.
- **Condition error in `when`:** fails the node, and `ignore_errors` on that node applies to it.
- **Reap timeout:** 5s, fixed by the spec. After KILL, a join waits at most grace + 5s for cancelled children to be reaped; anything still alive is reported as a survivor.

### Consequences

- Good: `spec/execution-model.md` §6 and §8 have no open cases.
- Good: statuses always describe the node's own fate, so a timeout is easy to locate in the report.
- Neutral: a cancelled `all` can take up to grace + 5s to complete when a child ignores TERM and is stuck after KILL.
- Bad: callers that need to know a plan did nothing (root skipped) must read the report, because the exit code is 0.

## More information

- Applied in: `spec/execution-model.md` (EM-32, EM-43 to EM-50).
- Tracker: T-0017.
