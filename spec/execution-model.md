# Execution model

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is normative for how a plan runs: the run lifecycle, the order in which modifiers apply, start order and concurrency, leaf processes, time limits, cancellation, external stops, and status propagation. It is OS-independent and describes what a plan and its processes can observe; how an implementation achieves it (process groups, Job Objects, run budgets, reports) is up to the implementation (for blokky-cli: [`docs/contracts/run-control.md`](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/run-control.md) and the design docs). Statements marked *provisional — verify in spike* depend on spike results. Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions). Rules carry IDs (`EM-n`) so that conformance cases can cite them; IDs of rules that moved to blokky-cli are not reused.

## 1. Run lifecycle

A run goes through two phases:

1. **Validation.** The plan is read, checked (encoding, character lint, YAML subset, schema, the static rules of [reference.md §8](reference.md#8-rules-the-schema-doesnt-express)), and its inputs are bound.
2. **Execution.** The root node runs. The run ends with a **run result** ([results.md](results.md)).

- **EM-1.** Any plan or input error ends the run in the validation phase: no node runs, and no process or probe starts.
- **EM-2.** All plan and input errors that can be found are reported together.
- **EM-3.** Once execution begins, the run always ends with a run result, including after failures, timeouts and external stops (§7), unless the implementation itself is killed.

## 2. Modifier application order

**EM-4.** Modifiers apply in this order, outermost first:

`when` → `timeout` → `lock` → `tempdir` → `cwd` → `env` → `container`/`become` → `services` → `finally` → repetition (`retry` | `while` | `until` | `for`) → `attempt_timeout` → kind (including `capture`).

Entering a node means applying each layer in this order; leaving it unwinds them in reverse.

| Layer | On entry | On exit |
|---|---|---|
| `when` | Evaluate the condition in the **parent's** scope. False: the node is `skipped` and nothing below happens. | — |
| `timeout` | Start the node's total timer. | Stop the timer. |
| `lock` | Acquire the lock, waiting at most `wait`. | Release the lock. |
| `tempdir` | Create the directory; it becomes the cwd. | Keep the directory (it isn't deleted). |
| `cwd`, `env` | Set the scope for everything inside. | — |
| `container`/`become` | Start the container / select the user. | Stop the container. |
| `services` | Start services and wait until ready. | Stop services (whole tree). |
| `finally` | — | Run the `finally` list once. |
| repetition | Run attempts or iterations. | — |
| `attempt_timeout` | Start the per-attempt timer for each attempt. | Stop it. |
| kind | Run the node's body. | — |

- **EM-5.** A node skipped by `when` takes no lock, creates no tempdir, starts no container or service, and runs no `finally`.
- **EM-6.** `timeout` covers everything from lock wait to the end of the last attempt, but not `finally`.
- **EM-7.** `finally` runs once per node, inside the node's tempdir, cwd, env, container and services, under its own `finally_timeout`, even after `timeout` fired.
- **EM-8.** Probes in `if`, `while`, `until` and `retry` conditions run in the node's own scope (after `cwd`, `env`, `container`, `become`); `when` probes run in the parent's scope.

## 3. Start order and concurrency

- **EM-9.** Children of `do` start one at a time, in declaration order.
- **EM-10.** Children of `all` and `any` and iterations of `for` start **in declaration (item) order**. With a concurrency limit N, at most N run at once, and the next one starts as soon as a slot frees, still in order.
- **EM-11.** An implementation MAY cap the effective concurrency of a node below its `concurrency` (or its default), for example to protect the machine (for blokky-cli: `max_concurrency`, default 16). A cap reduces parallelism only; it never changes start order, statuses or results.
- **EM-12.** `race` starts all children immediately, in declaration order.
- **EM-13.** The run result lists nodes in plan order, whatever the completion order. Only completion order, timings and the winners of `any`/`race` are non-deterministic.

## 4. Leaf processes

### 4.1 Launch

- **EM-14.** A leaf's program is resolved before launch: `exec` argv[0], or the shell binary for `script`, against `PATH` from the environment the run started with, never the cwd ([shells.md §4](shells.md#4-executable-resolution)).
- **EM-15.** Every leaf, with everything it starts, MUST be stoppable as one process tree. Leaves have no controlling terminal. (How: implementation-defined; for blokky-cli: own session and process group on Unix, own Job Object on Windows.)
- **EM-16.** A leaf's environment is the environment the run started with, plus the `env` and `export` mappings of every enclosing scope, innermost last; `BASH_ENV` and `ENV` are then cleared ([variables.md §7](variables.md#7-environment)).
- **EM-17.** A leaf's stdin is empty unless the plan sets `stdin`. A run never forwards its own stdin to leaves and never prompts.

### 4.2 Output

- **EM-18.** A leaf's stdout and stderr are always consumed while it runs, so a leaf never blocks on a full pipe, whatever the implementation keeps of them.
- **EM-19.** With `stderr: merge`, both streams share one pipe and their interleaving is kept.

### 4.3 Completion

- **EM-20.** A leaf **completes when its direct child process exits**. Output its descendants write after that is read for a bounded, implementation-defined time (for blokky-cli: `drain_timeout`, default 2s); if a descendant still holds the output open, the run result notes it.
- **EM-21.** At completion, the leaf's remaining process tree is stopped (graceful, then forced), unless the leaf sets `keep_descendants: true`.
- **EM-22.** Every descendant of every leaf is stopped no later than the end of the run, including when the run is stopped from outside (§7). Processes that deliberately escape (double-fork daemons, Windows breakaway) are handled on a best-effort basis. *Provisional — verify in spike #1*, including when the implementation itself is killed.
- **EM-23.** The leaf succeeds if its exit code is 0 or listed in `ok_exit`. A leaf killed by a signal (Unix) fails. The run result gives the exit code (an unsigned 32-bit value on Windows), the signal, and, if the run stopped the leaf, why (`killed_by`).
- **EM-24.** Captures are evaluated after completion and bound only if the leaf succeeded ([variables.md](variables.md)).

## 5. Time limits

All limits use a monotonic clock.

| Limit | Applies to | Default | Error |
|---|---|---|---|
| `timeout` | a node, total | none | `BK_TIMEOUT_TOTAL` |
| `attempt_timeout` | one attempt or iteration (body only) | none | `BK_TIMEOUT_ATTEMPT` |
| `defaults.leaf_timeout` | each leaf and probe without its own `timeout` | none | `BK_TIMEOUT_TOTAL` |
| probe `timeout` | one probe | 30s, or `leaf_timeout` if smaller | condition error (unless `timeout_result`) |
| `finally_timeout` | a node's `finally` list | 5m | attached to the node's error |

Implementations MAY let users change the 30s and 5m defaults and the grace period below; plans that need a specific value set it explicitly.

- **EM-25.** Nested limits combine: the effective limit at any point is the earliest deadline of all enclosing limits.
- **EM-26.** **When a limit fires**, every process tree under that limit gets the graceful stop request (SIGTERM on Unix; CTRL_BREAK on Windows when the leaf has a console, otherwise none), then, after the **grace period** (default 5s), is killed. The grace period comes **after** the limit, not inside it ([ADR 0003](../adr/0003-execution-defaults.md), Q-k).
- **EM-27.** The node whose own limit fired is `timed_out`; its error code is always present, and leaves under it carry `killed_by: timeout` or `attempt_timeout`.
- **EM-28.** `sleep` and `every` waits end immediately when their node is cancelled or a limit fires.

## 6. Cancellation

A node is **cancelled** when something outside it stops it:

- a failing sibling under `fail_fast: true` (`do`, `all`, `for`);
- a decided `any` (a sibling succeeded) or `race` (a sibling completed);
- an ancestor's `timeout` or `attempt_timeout`;
- an external stop of the whole run (§7).

Rules:

- **EM-29.** Cancellation propagates down: every running descendant is cancelled; nodes that haven't started never start.
- **EM-30.** Cancelled processes get the graceful stop request, then are killed after the grace period (EM-26).
- **EM-31.** `finally` of a cancelled node still runs, under `finally_timeout` (shortened during an external stop, §7).
- **EM-32.** **Joins confirm.** An `all`, `any` or `race` completes only after its cancelled children are confirmed: each direct child reaped and its tree killed. Confirmation waits at most the grace period plus a fixed **reap timeout of 5s**. Anything still alive then is listed as a survivor in the run result, and the join completes anyway.
- **EM-33.** A cancelled node never retries and never starts another iteration.

## 7. External stops

An implementation can stop a whole run from outside the plan, for example when a run budget runs out or the user interrupts it. How and when is implementation-defined (for blokky-cli: [run-control.md](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/run-control.md)). For the plan, an external stop means:

- **EM-55.** Every running node is cancelled (§6) with `BK_CANCELLED` and `detail.reason` naming the cause; leaves carry `killed_by` with the cause. Nodes that haven't started never start.
- **EM-56.** `finally` lists still run, but the implementation MAY shorten their `finally_timeout` and the grace period, down to zero, so the run ends in time.
- **EM-36.** `ignore_errors` never hides an external stop, an ancestor's timeout or an ancestor's cancellation.
- **EM-57.** The run ends with a run result whose status is `stopped`, with the cause ([results.md](results.md)).

## 8. Status

### 8.1 Node statuses

| Status | Meaning |
|---|---|
| `succeeded` | The node finished without failing. |
| `failed` | The node failed. With `ignore_errors: true` it also carries `ignored: true`. |
| `skipped` | The node didn't start: its `when` was false (`skip_reason: condition`), or it was never reached because its parent ended early (`skip_reason: not_reached`). |
| `timed_out` | The node's **own** `timeout` or `attempt_timeout` fired. |
| `cancelled` | The node was running and was stopped from outside (§6, §7). |

### 8.2 Propagation

([ADR 0009](../adr/0009-status-propagation.md))

- **EM-43.** A node is `timed_out` only if its own limit fired, and `cancelled` only if it was stopped from outside. A parent never inherits these statuses from a child: a parent whose child timed out or was cancelled is `failed` (or `cancelled`/`timed_out` for its own reasons), with the child's error as a cause.
- **EM-44.** A `do`, `all` or `any` whose children were **all skipped** is `succeeded`, and its `finally` runs.
- **EM-45.** `do` succeeds if no child failed (ignored failures don't count). `all` likewise. `any` succeeds if one child succeeded, or if no child failed (all skipped); it fails if no child succeeded and at least one failed.
- **EM-46.** A child that failed with `ignore_errors: true` is **not a success**: it doesn't fail its parent, but it doesn't win an `any` either; `any` goes on to the next alternative, and if none succeeds, the ignored failures are among its causes.
- **EM-47.** A condition error in `when` fails the node, and `ignore_errors` on that node applies to it. Since `when` is the first layer, no lock, tempdir or `finally` is involved.
- **EM-48.** `if` takes the status of the branch it ran; with a false condition and no `else`, it succeeds.
- **EM-49.** The children of an `all` stopped by a failing child are `cancelled` (running) or `skipped` with `not_reached` (unstarted), and the `all` fails with the first failure as its error.

### 8.3 Run status

- **EM-50.** The run's status is derived from the root node and external stops: `succeeded` (the root succeeded, or was skipped by its `when`), `failed` (the root failed, timed out or was cancelled by the plan's own rules), or `stopped` (an external stop, §7). How an implementation reports it (exit codes) is up to the implementation.

### 8.4 Error precedence

- **EM-51.** If a node's body fails and its `finally` also fails, the body error is primary and the `finally` error is attached. A failing `finally` fails an otherwise successful node.
- **EM-52.** When several children fail (`do` with `fail_fast: false`, `all`), the first failure in plan order is the primary error; the others are attached as causes. An `any` whose children all failed fails with `BK_ANY_ALL_FAILED` and every child error as a cause, in plan order.
- **EM-53.** Repetition errors (`BK_RETRIES_EXHAUSTED`, `BK_LOOP_MAX_REACHED`, `BK_TIMEOUT_TOTAL`) nest the last attempt's error.

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
| 28s | The `all` completes as `failed`, its error the integration tests' `BK_TIMEOUT_TOTAL` (EM-43, EM-49). |
| 28s | The root's `finally` runs `docker compose down` under `finally_timeout` (EM-7). |
| 31s | `finally` succeeds. The root is `failed` (its own timeout didn't fire), and so is the run (EM-50). |

## 10. Conformance

Every rule `EM-n` above has at least one conformance case in `conformance/cases/` that cites it. Timing rules are tested with the virtual clock where possible and with the tolerances in `conformance/README.md` otherwise.
