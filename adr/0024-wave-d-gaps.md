# 0024: Gaps found by the wave D conformance cases

- Status: accepted
- Date: 2026-11-07
- Questions: none from the brief; raised while writing and checking the wave D time-limit, cancellation, lock and service cases (tracker T-0064, F-0020; [review notes](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/review/conformance-wave-d.md))

## Context and problem statement

Three agents wrote the wave D cases (time limits and repetition timing, cancellation and external stops, modifier order, locks and services), and three more read them against the spec. They found no wrong expectations; one fragile duration bound and a duplicate lock case were fixed. The remaining gaps leave the status of a repeating node whose attempts timed out, the outcome of a fired `finally_timeout`, and several result fields undetermined, and the case format had no way to expect a run without a result. The maintainer decided H-1 and H-2 and accepted the batch L-1 to L-6 on 2026-11-07.

## Considered options

| Item | Options (chosen in bold) |
|---|---|
| H-1 a node whose own `attempt_timeout` fired, and which then failed | **`timed_out` only when the node's own error is a timeout code; a retry or loop ending with `BK_RETRIES_EXHAUSTED` or `BK_LOOP_MAX_REACHED` is `failed`, its timed-out entries `timed_out`**; `timed_out` whenever the node's own `attempt_timeout` fired in any attempt |
| H-2 when `finally_timeout` fires | **a new code, `BK_TIMEOUT_FINALLY`, attached like any `finally` error; the stopped `finally` node is `cancelled` with `killed_by: finally_timeout`**; reuse `BK_TIMEOUT_TOTAL` with `killed_by: finally_timeout` |
| L-1 to L-6 | **accepted as a batch** |

## Decision outcome

- **H-1.** A node is `timed_out` only when its own `timeout` or `attempt_timeout` fired and its error is that limit's code, `BK_TIMEOUT_TOTAL` or `BK_TIMEOUT_ATTEMPT`. A retry or loop that ends with `BK_RETRIES_EXHAUSTED` or `BK_LOOP_MAX_REACHED` is `failed`, and its repetition entries ended by `attempt_timeout` are `timed_out` (EM-27, EM-43, execution-model.md §8.1). The status matches the error, and the merged case that expects `failed` with `BK_RETRIES_EXHAUSTED` stands.
- **H-2.** When `finally_timeout` fires, the running `finally` nodes are cancelled, their leaves carry `killed_by: finally_timeout`, and the `finally` list fails with the new code `BK_TIMEOUT_FINALLY` (not retried), attached to the node's error like any `finally` error. It doesn't make the node `timed_out` (EM-7, EM-51, errors.md §5.2). A hung cleanup is told apart from a slow body.
- **L-1 Statuses and errors.**
  - The `BK_TIMEOUT_TOTAL` row says "except on repeating leaves" ([ADR 0018](0018-review-semantics.md) S-9); a per-attempt `defaults.leaf_timeout` fails the attempt with `BK_TIMEOUT_ATTEMPT` and `killed_by: attempt_timeout` (errors.md §5.2, execution-model.md §5).
  - When the node's own `timeout` fires during an attempt, the interrupted attempt is the last attempt, and its `BK_CANCELLED` is the error nested (EM-53).
  - `ended_by` gets `cancelled`, for a repetition ended by cancellation or an external stop; the count includes the cancelled attempt or iteration. A `for` stopped by `fail_fast` ends with `failure`; one that ran all items ends with `items`, even if some failed (results.md §3, reference.md §5.7).
  - For a `stopped` run, the run's error is the root's `BK_CANCELLED`, and `detail.reason` names the cause (EM-57, results.md §2).
  - `ignored` is absent unless `ignore_errors` hid a failure (results.md §3).
- **L-2 Durations.** A node's duration runs from its start (after its `when` passed) to its completion, and includes lock wait, setup, services and `finally`; a leaf's duration ends as EM-68 says. New rule EM-70; results.md lists `duration` per node.
- **L-3 Repetition timing.** In `while`, the `every` wait comes first, then the condition check, right before each iteration (reference.md §5.3, §5.6).
- **L-4 Services.**
  - The run result lists the services that started, in list order. A service that exits before it is ready ends `exited`, with its exit code; one stopped by a timeout or cancellation during startup ends `never_ready`. `ready_after` is measured from the node's start (results.md §3, reference.md §4.9).
  - When services fail to start, the body and `finally` nodes are `skipped` with `not_reached`, and there is no `finally` status (EM-63).
  - EM-15's process-tree and console requirements also cover services and probes, so their graceful stop works on Windows.
- **L-5 Locks and tempdirs.**
  - Two nodes of the same run that use the same lock name exclude each other, as two runs do; the order among waiters is unspecified (EM-60, reference.md §4.4).
  - `tempdir: { remove: false }`, the default, keeps the directory (reference.md §4.5).
- **L-6 Conformance format.**
  - A case with a `kill` action may use `expect: { no_result: true }`, optionally with `files` and `invocations`, and checks what survives with `after_run`; such cases list the `kill` feature (CF-22, CF-25, new CF-65).
  - The testkit's `sleep` gets `--tag TEXT`, which prefixes each recorded signal line, so cases can show EM-65's reverse stop order (TK-14).
  - EM-32's survivor clause is exempt: the testkit can't make a process that survives a forced kill. EM-60's per-user scope (a second OS user) and EM-26's `graceful: none` (a program that detaches from its console) are noted as not covered.

### Consequences

- Good: a node's status always agrees with its error code, so `retry:` conditions, `result: error` and statuses tell the same story.
- Good: a hung `finally` has its own code and `killed_by` value, and cancellations, services and durations are fully determined, so the wave D cases can assert them on every OS.
- Neutral: one more error code and `killed_by` value, a third expectation form for kill cases, and one more testkit flag.

## More information

- Applied in: `spec/execution-model.md`, `spec/errors.md`, `spec/results.md`, `spec/reference.md`, `conformance/README.md`, `conformance/testkit-interface.md`.
- Tracker: T-0064; finding F-0020.
