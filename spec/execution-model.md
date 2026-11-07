# Execution model

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is normative for how a plan runs: the run lifecycle, the order in which modifiers apply, start order and concurrency, leaf processes, time limits, cancellation, external stops, and status propagation. It is OS-independent and describes what a plan and its processes can observe; how an implementation achieves it (process groups, Job Objects, run budgets, reports) is up to the implementation (for blokky-cli: [`docs/contracts/run-control.md`](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/run-control.md) and the design docs). Statements marked *provisional — verify in spike* depend on spike results. Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions). Rules carry IDs (`EM-n`) so that conformance cases can cite them; IDs of rules that moved to blokky-cli are not reused.

## 1. Run lifecycle

A run goes through two phases:

1. **Validation.** The plan is read, checked (encoding, character lint, YAML subset, schema, the static rules of [reference.md §8](reference.md#8-rules-beyond-the-schema)), its inputs and `vars` are bound, and its `from_env` references are resolved ([variables.md](variables.md), VA-40).
2. **Execution.** The root node runs. The run ends with a **run result** ([results.md](results.md)).

- **EM-1.** Any plan or input error ends the run in the validation phase: no node runs, and no process or probe starts.
- **EM-2.** All plan and input errors that can be found are reported together.
- **EM-3.** Once execution begins, the run always ends with a run result, including after failures, timeouts and external stops (§7), unless the implementation itself is killed.

## 2. Modifier application order

**EM-4.** Modifiers apply in this order, outermost first:

`when` → `timeout` → `lock` → `tempdir` → `cwd` → `env` → `container` → `services` → `finally` → repetition (`retry` | `while` | `until` | `for`) → `attempt_timeout` → kind (including `capture`).

Entering a node means applying each layer in this order; leaving it unwinds them in reverse.

| Layer | On entry | On exit |
|---|---|---|
| `when` | Evaluate the condition in the **parent's** scope. False: the node is `skipped` and nothing below happens. | — |
| `timeout` | Start the node's total timer. | Stop the timer. |
| `lock` | Acquire the lock, waiting at most `wait`. | Release the lock. |
| `tempdir` | Create the directory; it becomes the cwd. | Keep the directory, unless `remove` says to delete it. |
| `cwd`, `env` | Set the scope for everything inside. | — |
| `container` | Start the container. | Stop the container. |
| `services` | Start services and wait until ready. | Stop services (whole tree). |
| `finally` | — | Run the `finally` list once. |
| repetition | Run attempts or iterations. | — |
| `attempt_timeout` | Start the per-attempt timer for each attempt. | Stop it. |
| kind | Run the node's body. | — |

- **EM-5.** A node skipped by `when` takes no lock, creates no tempdir, starts no container or service, and runs no `finally`. Only the node itself appears in the run result (RS-7).
- **EM-6.** `timeout` covers everything from lock wait to the end of the last attempt, but not `finally`.
- **EM-7.** `finally` runs once per node, inside the node's tempdir, cwd, env, container and services, under its own `finally_timeout`, even after `timeout` fired, provided the node got past every layer outside it (EM-63). When `finally_timeout` fires, the running `finally` nodes are cancelled (§6) and their leaves carry `killed_by: finally_timeout`; the `finally` list fails with `BK_TIMEOUT_FINALLY`, which is attached to the node's error like any `finally` error (EM-51) and doesn't make the node `timed_out` (EM-27; [ADR 0024](../adr/0024-wave-d-gaps.md)).
- **EM-8.** Probes in `if`, `assert`, `while`, `until` and `retry` conditions run in the node's own scope (after `cwd`, `env`, `container`); `when` probes run in the parent's scope.
- **EM-70.** A node's duration runs from its start, after its `when` passed, to its completion, and includes lock wait, setup (tempdir, container), services and `finally`. For a leaf's process, EM-68 defines when it ends; the drain and reap time after that are recorded separately and don't end the node's duration ([ADR 0024](../adr/0024-wave-d-gaps.md)).

### 2.1 Locks and services

- **EM-60.** A `lock` is acquired after the node's `timeout` starts and before anything else in the node; waiting counts against `timeout`. It is held until the node ends (after `finally`) and released when the run's process dies. Two nodes of the same run that use the same lock name exclude each other, as nodes of two runs do; the order among waiters is unspecified ([ADR 0024](../adr/0024-wave-d-gaps.md)). A waiting node checks the lock again at most 250ms after the end of its previous check, as for readiness (EM-62), so it gets a released lock within that bound ([ADR 0026](../adr/0026-runtime-edge-cases.md)).
- **EM-61.** `services` start after `container` and before `finally` and the body. They start one at a time, in list order, each after the previous one is ready. The body starts when every service is ready.
- **EM-62.** Readiness is polled, with at most 250ms between the end of one check and the start of the next, until the `ready:` condition holds, for at most `ready_timeout` (default 30s), within the node's `timeout`.
- **EM-63.** **A failure outside `finally`.** `finally` runs only when the node got past every layer outside it (§2): it runs inside them (EM-4, EM-7). When one of those layers fails the node, the body and the node's `finally` don't run: their nodes are `skipped` with `not_reached`, and the run result records no `finally` status. This covers a lock not acquired (`BK_LOCK_TIMEOUT`), a tempdir not created (`BK_TEMPDIR_FAILED`), an invalid or unmapped cwd (`BK_CWD_INVALID`, `BK_CWD_UNMAPPED`), an `env` value whose variable isn't bound (`BK_UNDEFINED_VARIABLE`), a container that doesn't start (`BK_CONTAINER_FAILED`), a service that exits before it is ready or isn't ready in time (`BK_SERVICE_EXITED`, `BK_SERVICE_NOT_READY`), and the node's `timeout` or a cancellation during any of them. The layers already entered are unwound: services already started are stopped, a started container is stopped, the lock is released ([ADR 0024](../adr/0024-wave-d-gaps.md), [ADR 0026](../adr/0026-runtime-edge-cases.md)).
- **EM-64.** If a ready service with `on_exit: fail` exits on its own, the body is cancelled (§6) and the node fails with `BK_SERVICE_EXITED`; `finally` still runs, with the remaining services. With `on_exit: ignore`, the exit is recorded and nothing else happens. A service that exits after the body ended (during `finally`) is recorded and is not a failure.
- **EM-65.** After `finally`, services are stopped in reverse list order, each as a whole process tree (graceful, then forced, EM-26). An exit caused by stopping is not a failure. Services belong to the node's scope, not to its body: when the node's own `timeout` fires while the body runs, the body's processes are stopped, and the services keep running so that `finally` can use them; they are stopped after it, as here ([ADR 0026](../adr/0026-runtime-edge-cases.md)).

## 3. Start order and concurrency

- **EM-9.** Children of `do` start one at a time, in declaration order.
- **EM-67.** A `return` ends its nearest enclosing sequence (a `do` list, a loop body or a `finally` list; `then` and `else` are transparent): its remaining nodes don't start and are `skipped` with `skip_reason: returned`, and the node that owns the sequence completes normally, including its `finally` ([reference.md §2.13](reference.md#213-return)).
- **EM-10.** Children of `all` and `any` and iterations of `for` start **in declaration (item) order**. With a concurrency limit N, at most N run at once, and the next one starts as soon as a slot frees, still in order.
- **EM-11.** An implementation MAY cap the effective concurrency of a node below its `concurrency` (or its default), for example to protect the machine (for blokky-cli: `max_concurrency`, default 16). A cap reduces parallelism only; it never changes start order, statuses or results.
- **EM-12.** `race` starts all children immediately, in declaration order.
- **EM-58.** The first `race` child to complete decides: the race takes its outcome (an ignored failure counts as not failed), and the other children are cancelled and confirmed (EM-32) before the race completes. Skipped children don't take part; if all are skipped, the race succeeds.
- **EM-59.** In `race` and `any`, only the deciding child's captures are bound.
- **EM-13.** The run result lists nodes in plan order, whatever the completion order. Only completion order, timings and the winners of `any`/`race` are non-deterministic.

## 4. Leaf processes

### 4.1 Launch

- **EM-14.** A leaf's program is resolved before launch: `exec` argv[0], or the shell binary for `script`, against `PATH` from the environment the run started with, never the cwd ([shells.md §4](shells.md#4-executable-resolution)). A container leaf's program resolves inside the container instead (CP-15).
- **EM-15.** Every leaf, service and probe, with everything it starts, MUST be stoppable as one process tree. Leaves have no controlling terminal on Unix; on Windows they have no visible console and receive no user input. (How: implementation-defined; for blokky-cli: own session and process group on Unix, own Job Object on Windows.) Every Windows leaf, service and probe MUST have a console the graceful stop can reach: its own hidden console, or its own process group on a shared hidden console, so that CTRL_BREAK can be delivered (EM-26; [ADR 0020](../adr/0020-conformance-gaps.md), [ADR 0024](../adr/0024-wave-d-gaps.md)).
- **EM-16.** A leaf's environment is built as in VA-39: the environment the run started with, the `env` and `export` mappings of every enclosing scope, innermost last, and the variables Blokky sets (VA-44); `BASH_ENV` and `ENV` are then cleared ([variables.md §7](variables.md#7-environment)).
- **EM-17.** A leaf's stdin is empty unless the plan sets `stdin`. A run never forwards its own stdin to leaves and never prompts.

### 4.2 Output

- **EM-18.** A leaf's stdout and stderr are always consumed while it runs, so a leaf never blocks on a full pipe, whatever the implementation keeps of them.
- **EM-19.** With `stderr: merge`, both streams share one pipe and their interleaving is kept.

### 4.3 Run-owned files

- **EM-69.** Files and directories a run creates for itself (script files, capture files, tempdirs, env files) are created new, under a per-user root that only the run's user can write: never at an existing path and never through an existing symbolic link. Removing them, at node end (`tempdir.remove`) or later, never follows symbolic links or junctions, never crosses a file system boundary and never removes anything outside the file's own tree. A removal stopped by a mount point keeps the mount point and its ancestors; it doesn't fail the node, and the run result's `warnings` report it as partial, with the kept path ([results.md §2](results.md#2-the-run), [ADR 0027](../adr/0027-spike-findings.md)). The scripts directory a container sees holds only the run's script files.

### 4.4 Completion

- **EM-20.** A leaf **completes when its direct child process exits**. Output its descendants write after that is read for a bounded, implementation-defined time of at least 1s (for blokky-cli: `drain_timeout`, default 2s); if a descendant still holds the output open, the run result notes it.
- **EM-21.** At completion, the leaf's remaining process tree is stopped (graceful, then forced), unless the leaf sets `keep_descendants: true` or `detach`.
- **EM-68.** **Order at completion.** When a leaf's direct child exits, these steps happen in this order ([ADR 0018](../adr/0018-review-semantics.md)):
  1. the leaf's duration ends;
  2. output is drained until EOF or the drain bound (EM-20);
  3. the remaining process tree is stopped (EM-21), unless `keep_descendants` says otherwise: the step ends when no live process of the leaf's OS grouping (EM-22) is left;
  4. captures and the leaf's status are fixed (EM-24), and only then does the next node start.

  Captures therefore include output written during the drain, and the next sibling never overlaps a dying descendant. The time spent in steps 2 and 3 is recorded separately from the leaf's duration ([ADR 0027](../adr/0027-spike-findings.md)).
- **EM-22.** **Descendants at run end.** Except for leaves with `keep_descendants: detach` (which the run never stops and lists in the run result), descendants are stopped by the end of the run, also when it is stopped from outside (§7), with a strength that depends on how they relate to the leaf ([ADR 0018](../adr/0018-review-semantics.md)):
  - the implementation MUST stop every process in the leaf's own OS grouping (its process group or session on Unix, its job on Windows);
  - it SHOULD do the same when the implementation itself is killed, and documents per OS how far it achieves this (for blokky-cli: the run-control contract);
  - processes that leave the grouping on purpose (double-fork daemons, `setsid`, Windows breakaway) are stopped on a best-effort basis.
- **EM-23.** The leaf succeeds if its exit code is 0 or listed in `ok_exit`. A leaf killed by a signal (Unix) fails. The run result gives the exit code (an unsigned 32-bit value on Windows), the signal, and, if the run stopped the leaf, why (`killed_by`).
- **EM-24.** Captures are evaluated after completion and bound only if the leaf succeeded ([variables.md](variables.md)).

## 5. Time limits

All limits use a monotonic clock.

| Limit | Applies to | Default | Error |
|---|---|---|---|
| `timeout` | a node, total | none | `BK_TIMEOUT_TOTAL` |
| `attempt_timeout` | one attempt or iteration (body only) | none | `BK_TIMEOUT_ATTEMPT` |
| `defaults.leaf_timeout` | each leaf without its own `timeout`; on a leaf with `retry`, `while` or `until`, each attempt or iteration | none | `BK_TIMEOUT_TOTAL`; `BK_TIMEOUT_ATTEMPT` per attempt (`killed_by: attempt_timeout`) |
| probe `timeout` | one probe | 30s, or `leaf_timeout` if smaller (CO-29) | condition error (unless `timeout_result`) |
| `finally_timeout` | a node's `finally` list | 5m | `BK_TIMEOUT_FINALLY`, attached to the node's error |

Implementations MAY let users change the 30s and 5m defaults and the grace period below; plans that need a specific value set it explicitly.

- **EM-25.** Nested limits combine: the effective limit at any point is the earliest deadline of all enclosing limits. The one exception is `finally`: a `finally` list's deadline is its own `finally_timeout`, measured from when it starts, whatever limits of the node or its ancestors have expired (only an external stop may shorten it, EM-56). An ancestor's `finally` starts after the nested ones have ended.
- **EM-26.** **When a limit fires**, every process tree under that limit gets the graceful stop request (SIGTERM on Unix; CTRL_BREAK on Windows, through the leaf's console, EM-15), then, after the **grace period** (default 5s), is killed. A process that has left its console (a Windows program that detached itself) has no graceful channel: it is killed at once, and the run result records `graceful: none` for it. The grace period comes **after** the limit, not inside it ([ADR 0003](../adr/0003-execution-defaults.md), Q-k). For a node's own `timeout`, the processes under the limit are those of the body: the node's services are part of its scope and keep running for `finally` (EM-65); a `timeout` that fires during service startup stops the services already started (EM-63).
- **EM-27.** The node whose own limit fired and ended it is `timed_out`: its error is that limit's code, `BK_TIMEOUT_TOTAL` or `BK_TIMEOUT_ATTEMPT`, which is always present, and leaves under it carry `killed_by: timeout` or `attempt_timeout`. A repeating node whose own `attempt_timeout` (or per-attempt `defaults.leaf_timeout`) fired, and which then ends with `BK_RETRIES_EXHAUSTED` or `BK_LOOP_MAX_REACHED`, is `failed`; its repetition entries ended by `attempt_timeout` are `timed_out` ([ADR 0024](../adr/0024-wave-d-gaps.md)).
- **EM-28.** `sleep` and `every` waits end immediately when their node is cancelled or a limit fires.

## 6. Cancellation

A node is **cancelled** when something outside it stops it:

- a failing sibling under `fail_fast: true` (`do`, `all`, `for`);
- a decided `any` (a sibling succeeded) or `race` (a sibling completed);
- an ancestor's `timeout` or `attempt_timeout`;
- for nodes of a `finally` list, that list's `finally_timeout` (EM-7);
- an external stop of the whole run (§7).

Rules:

- **EM-29.** Cancellation propagates down: every running descendant is cancelled; nodes that haven't started never start.
- **EM-30.** Cancelled processes get the graceful stop request, then are killed after the grace period (EM-26).
- **EM-31.** `finally` of a cancelled node still runs, under `finally_timeout` (shortened during an external stop, §7).
- **EM-32.** **Joins confirm.** An `all`, `any` or `race` completes only after its cancelled children are confirmed. A cancelled child is confirmed when it has completed, its `finally` included (bounded by its `finally_timeout`, EM-31), so cleanup never overlaps the nodes after the join. Each process being killed is waited for at most the grace period plus a **reap timeout** (implementation-defined, at least 1s; for blokky-cli: 5s); anything still alive then is listed as a survivor in the run result, and confirmation goes on without it ([ADR 0018](../adr/0018-review-semantics.md)).
- **EM-33.** A cancelled node never retries and never starts another iteration.

## 7. External stops

An implementation can stop a whole run from outside the plan, for example when a run budget runs out or the user interrupts it. How and when is implementation-defined (for blokky-cli: [run-control.md](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/run-control.md)). For the plan, an external stop means:

- **EM-55.** Every running node is cancelled (§6) with `BK_CANCELLED` and `detail.reason` naming the cause; leaves carry `killed_by` with the cause. Nodes that haven't started never start.
- **EM-56.** `finally` lists still run, but the implementation MAY shorten their `finally_timeout` and the grace period, down to zero, so the run ends in time.
- **EM-36.** `ignore_errors` never hides an external stop, an ancestor's timeout or an ancestor's cancellation.
- **EM-57.** The run ends with a run result whose status is `stopped`, with the cause ([results.md](results.md)). The run's error is the root's error. When the stop interrupted unfinished work, that is the root's `BK_CANCELLED`, whose `detail.reason` names the cause ([ADR 0024](../adr/0024-wave-d-gaps.md)). When the body had already failed before the stop arrived (for example, the stop came during `finally`), the root keeps the body's error (EM-51) and the run's status is still `stopped` ([ADR 0025](../adr/0025-open-points.md)).

## 8. Status

### 8.1 Node statuses

| Status | Meaning |
|---|---|
| `succeeded` | The node finished without failing. |
| `failed` | The node failed. With `ignore_errors: true` it also carries `ignored: true`. |
| `skipped` | The node didn't start: its `when` was false (`skip_reason: condition`), it was never reached because its parent ended early (`skip_reason: not_reached`), a `return` ended its sequence before it (`skip_reason: returned`), a `host:` condition was false on this machine (`skip_reason: pruned`, CO-7), or it is in the branch of an `if` that didn't run (`skip_reason: not_taken`; `pruned` wins when a `host:` condition decided the branch). |
| `timed_out` | The node's **own** `timeout` or `attempt_timeout` fired and ended it: its error is `BK_TIMEOUT_TOTAL` or `BK_TIMEOUT_ATTEMPT` (EM-27). A retry or loop that ends with `BK_RETRIES_EXHAUSTED` or `BK_LOOP_MAX_REACHED` is `failed`, even if its attempts timed out. With `ignore_errors: true` it also carries `ignored: true`. |
| `cancelled` | The node was running and was stopped from outside (§6, §7). |

### 8.2 Propagation

([ADR 0009](../adr/0009-status-propagation.md))

- **EM-43.** A node is `timed_out` only if its own limit fired and its error is that limit's timeout code (EM-27), and `cancelled` only if it was stopped from outside. A parent never inherits these statuses from a child: a parent whose child failed, timed out or was cancelled is `failed` (or `cancelled`/`timed_out` for its own reasons).
- **EM-44.** A `do`, `all` or `any` whose children were **all skipped** is `succeeded`, and its `finally` runs.
- **EM-45.** `do` succeeds if no child failed (ignored failures don't count). `all` likewise. `any` succeeds if one child succeeded, or if no child failed (all skipped); it fails if no child succeeded and at least one failed. A child of `any` skipped by its `when` doesn't take part: an ordered `any` moves on to the next child.
- **EM-46.** A child that failed with `ignore_errors: true` is **not a success**: it doesn't fail its parent, but it doesn't win an `any` either; `any` goes on to the next alternative, and if none succeeds, the ignored failures are among its causes.
- **EM-47.** A condition error in `when` fails the node, and `ignore_errors` on that node applies to it. Since `when` is the first layer, no lock, tempdir or `finally` is involved, and the node records only its error and its `when` probes (RS-8).
- **EM-48.** `if` takes the status of the branch it ran; with a false condition and no `else`, it succeeds.
- **EM-49.** The children of an `all` stopped by a failing child are `cancelled` (running) or `skipped` with `not_reached` (unstarted), and the `all` fails with the first failure as its error.

### 8.3 Run status

- **EM-50.** The run's status is derived from the root node and external stops: `succeeded` (the root succeeded, or was skipped by its `when`), `failed` (the root failed, timed out or was cancelled by the plan's own rules), or `stopped` (an external stop, §7). How an implementation reports it (exit codes) is up to the implementation.

### 8.4 Error precedence

- **EM-51.** If a node's body fails and its `finally` also fails (including by `finally_timeout`, `BK_TIMEOUT_FINALLY`, EM-7), the body error is primary and the `finally` error is attached. A failing `finally` fails an otherwise successful node.
- **EM-66.** **A failed group carries its child's error.** When a `do`, `all`, `if`, `for` iteration or other group fails because a child failed, the group's error is that child's error itself (same code, `detail` and `node`), not a wrapper. Causes the group attaches (EM-51, EM-52) belong to the group's error only; the child's own recorded error is unchanged. So `retry:` conditions and `result: error` see the real cause, at any nesting depth ([ADR 0016](../adr/0016-fixes-from-examples.md)).
- **EM-52.** When several children fail (`do` with `fail_fast: false`, `all`), the first failure in plan order is the group's error; the others are attached to it as causes. An `any` whose children all failed fails with `BK_ANY_ALL_FAILED` and every child error as a cause, in plan order.
- **EM-53.** Repetition errors (`BK_RETRIES_EXHAUSTED`, `BK_LOOP_MAX_REACHED`, `BK_TIMEOUT_TOTAL`) nest the last attempt's error. When the node's own `timeout` fires during an attempt, the attempt it interrupted is the last attempt, its repetition entry is `cancelled`, and that attempt's error, `BK_CANCELLED`, is the one nested ([ADR 0024](../adr/0024-wave-d-gaps.md), [ADR 0026](../adr/0026-runtime-edge-cases.md)).

## 9. Worked example: a cancellation timeline

```yaml
blokky: 1.0
timeout: 1m
finally:
  - exec: [docker, compose, down]
all:
  - name: unit tests
    exec: [dotnet, test, tests/Unit]
  - name: integration tests
    exec: [dotnet, test, tests/Integration]
    timeout: 20s
```

With the defaults (grace 5s, reap timeout 5s, `finally_timeout` 5m):

| Time | Event |
|---|---|
| 0s | The root's 1m timer starts. Both children start, in declaration order. |
| 20s | The integration tests' own `timeout` fires: SIGTERM to that tree (EM-26). |
| 23s | The integration process exits after the signal. The node is `timed_out` with `BK_TIMEOUT_TOTAL`. |
| 23s | `fail_fast` cancels the unit tests: SIGTERM to that tree (EM-29, EM-30). |
| 28s | The grace period ends; the unit tests are still running: SIGKILL. |
| 28s | The process is reaped at once (the reap timeout would allow up to 33s). The unit tests are `cancelled` (EM-32). |
| 28s | The `all` completes as `failed`, its error the integration tests' `BK_TIMEOUT_TOTAL` (EM-49, EM-66). |
| 28s | The root's `finally` runs `docker compose down` under `finally_timeout` (EM-7). |
| 31s | `finally` succeeds. The root is `failed` (its own timeout didn't fire), and so is the run (EM-50). |

If the unit tests were a group with its own `finally` (say, uploading logs for 20s), the `all` would complete only after that `finally` ended, at about 48s, before the root's `finally` starts (EM-32).

## 10. Conformance

Every rule `EM-n` above has at least one conformance case in `conformance/cases/` that cites it, or is listed in `conformance/README.md` as not testable through the run result, with the reason (CF-51). Timing rules are tested with the virtual clock where possible and with the tolerances in `conformance/README.md` otherwise.
