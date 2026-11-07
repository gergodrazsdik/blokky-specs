# Run results

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document defines the **run result**: the abstract outcome of a run that every implementation MUST be able to produce, and that conformance cases assert on. It fixes what is recorded, not how it is serialized; for blokky-cli the run result is serialized as the JSON run report ([output-contract.md](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/output-contract.md)). Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions). Rules carry IDs (`RS-n`).

## 1. Principles

- **RS-1.** Every run that reaches execution ends with a run result (EM-3). A run that fails validation ends with its plan and input errors instead (EM-1, EM-2).
- **RS-2.** The run result contains no secret value: secrets are masked as described in [variables.md §9](variables.md#9-secrets), and secret outputs are marked without a value.
- **RS-3.** Nodes appear in plan order, as a tree mirroring the plan. Only the fields listed as non-deterministic (§6) may differ between two runs of the same plan with the same inputs and the same process behaviour.
- **RS-4.** Implementations MAY record more than this document lists; conformance cases assert only on what is listed here.

## 2. The run

| Field | Meaning |
|---|---|
| id | The run id: unique and sortable, also exported to leaves as `BLOKKY_RUN_ID` (VA-44). |
| plan | The plan's SHA-256 and the spec version from `blokky:`. |
| inputs | Each input's value and its source (supplied, or `default`), in declaration order. |
| status | `succeeded`, `failed` or `stopped` (EM-50). |
| stop cause | For `stopped`: why the run was stopped from outside (implementation-defined values, for example `budget`, `interrupt`). |
| error | The run's primary error (§5): the root node's error; for `stopped`, the root's `BK_CANCELLED`, whose `detail.reason` names the cause (EM-57). None on success. |
| outputs | Each `outputs` name with its final value, no value (`null`) if unbound, or marked secret ([variables.md §8](variables.md#8-outputs)). |
| warnings | Warnings the implementation raised at validation or run time (for example a short secret that couldn't be masked). |
| nodes | The root node's result (§3). |

## 3. Nodes

| Field | Applies to | Meaning |
|---|---|---|
| id | all | The node's path id. |
| kind | all | The node's kind. |
| name | if set | The raw `name` template. |
| status | all | `succeeded`, `failed`, `skipped`, `timed_out` or `cancelled` ([execution-model.md §8](execution-model.md#8-status)). |
| ignored | failed and timed-out nodes | `true` when `ignore_errors` hid the failure from the parent; absent otherwise. |
| skip reason | skipped nodes | `condition`, `not_reached`, `returned`, `pruned` (a `host:` condition was false, CO-7), or `not_taken` (the branch of an `if` that didn't run, unless a `host:` condition decided it: then `pruned`). |
| error | failed, timed out, cancelled | The node's error (§5). |
| repetition | `retry`, `while`, `until`, `for` | The number of attempts or iterations, including one that was cancelled; what ended them (`ended_by`: `success` for `retry`; `condition` for `while`/`until`; `items` for a `for` that ran all its items, even if some failed; or `max`, `timeout`, `cancelled` (cancellation or an external stop), or `failure`, which includes a `for` stopped by `fail_fast` and a condition error that ended the repetition, CO-40); the last condition result (`true`, `false`, `error`); and for each attempt or iteration its index, rendered name, item, status and error (an entry ended by `attempt_timeout` is `timed_out`, EM-27). Entries are listed in index order. |
| children | groups, `if` | The children's results, in plan order. |
| finally | nodes with `finally` | The `finally` list's results and its status. |
| lock wait | nodes with `lock` | How long the node waited for its lock. |
| services | nodes with `services` | For each service that started, in list order (services that never started are absent): its name; when it became ready, measured from the node's start; and how it ended: stopped by the run; exited with its exit code, also when it exited before it was ready; or never ready, when it wasn't ready within `ready_timeout` or was stopped by a timeout or cancellation during startup ([ADR 0024](../adr/0024-wave-d-gaps.md)). |
| duration | nodes that started | From the node's start to its completion (EM-70). |
| messages | `log`, `fail`, `assert` | The rendered message and, for `log`, its level. |
| probes | nodes whose conditions ran probes | For each executed probe, in execution order: the command, exit code and result (`true`, `false`, `error`). Its invocation follows the leaf rules (§3.1): masked, element 0 as written, or the resolved shell path for a `script` probe. |
| bindings | `exec`, `script`, `set`, loops, `tempdir` | The names of the variables the node bound by `capture`, `set`, `collect` or `tempdir.as` (never their values). |

### 3.1 Leaves

| Field | Meaning |
|---|---|
| program | The resolved absolute path of argv[0] or of the shell, as found on `PATH` or against the cwd; symbolic links aren't followed (SH-29). |
| invocation | The argv as run (masked), including the shell invocation for `script`. For `exec`, element 0 is argv[0] as written (`program` holds the resolved path); for `script`, element 0 is the resolved shell path. |
| cwd | The leaf's working directory (on the host; for a container leaf, also the container path). |
| exit code | The exit code (an unsigned 32-bit value on Windows), if the process exited. |
| signal | The terminating signal (Unix), if any. |
| killed by | If the run stopped the leaf: `timeout`, `attempt_timeout`, `finally_timeout` (EM-7), `cancel`, or the external stop's cause. |
| graceful | `none` when the leaf had left its console, so it had no graceful stop channel and was killed at once (EM-26). |
| descendants held output | Whether a descendant kept the output open after the leaf completed (EM-20). |
| survivors | Processes still alive after a join's reap timeout (EM-32). |
| left running | For `keep_descendants: detach`: the processes left running after the run (program and process id, EM-22). |
| container | The engine, image digest and container id (CP-6), and whether labelling was disabled for Blokky's mounts (CP-37). |

How much of a leaf's output the run result keeps (if any) is implementation-defined; conformance cases assert on output only through captures, `result:` conditions and outputs.

## 4. Statuses and outcomes

- **RS-5.** Node statuses and their propagation are defined in [execution-model.md §8](execution-model.md#8-status); the run status in EM-50.
- **RS-6.** A node that never started has its id, kind, name (if set), status `skipped` and skip reason, plus the probes its `when` ran (CO-31), and no other result fields: no duration, error or bindings.

## 5. Errors

| Field | Meaning |
|---|---|
| code | A built-in `BK_` code ([errors.md](errors.md)) or a user code. |
| message | Human-readable, masked. Not asserted on by conformance cases. |
| node | The id of the node the error belongs to. |
| detail | The code's machine-readable fields ([errors.md](errors.md)). |
| causes | Nested errors, in order: the last attempt's error, aggregated child errors in plan order, an attached `finally` error. |
| context | Extra context, for example an assertion's message and code on a condition error. |
| iteration, item | For an error raised inside a loop iteration or a retry attempt: its index and, for `for`, its item (masked like other values), so the causes of a `fail_fast: false` loop say which item failed. |

## 6. Non-deterministic fields

Timestamps and durations; completion order; the winners of `any` and `race`; survivors; process ids; anything an implementation records beyond §2–§5. Conformance cases MUST NOT assert on them exactly; timing rules are checked with tolerances or a virtual clock ([conformance/README.md](../conformance/README.md)).
