# Execution model

Status: **draft** (spec 0.1, not yet finalized)

This document is normative for how a plan runs: the run lifecycle, the order in which modifiers apply, start order and concurrency, leaf processes, time limits, cancellation, the run budget and shutdown, and status propagation. It is OS-independent. How each OS implements process control (sessions, Job Objects, the lifeline) is in the blokky-cli design docs; statements marked *provisional — verify in spike* depend on spike results. Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions). Rules carry IDs (`EM-n`) so that conformance cases can cite them.

## 1. Run lifecycle

A `blokky run` goes through these phases:

1. **Pre-run.** Read the plan, run the character lint, parse, validate (schema, [reference.md §8](reference.md#8-rules-the-schema-doesnt-express), lint at severity `error`), load config, and bind inputs.
2. **Start.** Create the run id, the run dir and the registry entry, and take the run's advisory lock.
3. **Execute** the root node.
4. **Finish.** Write `report.json` (atomically), print the report on stdout, release the lock, and exit.

- **EM-1.** Any error in the pre-run phase ends the run with the pre-run envelope on stdout and the matching exit code. No run id, run dir, process, probe or validator call exists at that point, and there is nothing to clean.
- **EM-2.** All pre-run errors that can be found are reported together.
- **EM-3.** Once the start phase begins, a report is always written, including after failures, timeouts, budget exhaustion and shutdown (but not after a SIGKILL of Blokky itself).

## 2. Modifier application order

**EM-4.** Modifiers apply in this order, outermost first:

`when` → `timeout` → `lock` → `tempdir` → `cwd` → `env` → `container`/`become` → `services` → `finally` → repetition (`retry` | `while` | `until` | `for`) → `attempt_timeout` → kind (including `capture`).

Entering a node means applying each layer in this order; leaving it unwinds them in reverse.

| Layer | On entry | On exit |
|---|---|---|
| `when` | Evaluate the condition in the **parent's** scope. False: the node is `skipped` and nothing below happens. | — |
| `timeout` | Start the node's total timer. | Stop the timer. |
| `lock` (*later*) | Acquire the lock, waiting at most `wait`. | Release the lock. |
| `tempdir` | Create the directory; it becomes the cwd. | Keep the directory (it is an artefact). |
| `cwd`, `env` | Set the scope for everything inside. | — |
| `container`/`become` (*later*) | Start the container / select the user. | Stop the container. |
| `services` (*later*) | Start services and wait until ready. | Stop services (whole tree). |
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
- **EM-11.** The effective concurrency is the minimum of the node's `concurrency` (or its default) and the config key `max_concurrency` (default 16). The cap applies per node, not per run.
- **EM-12.** `race` (*later*) starts all children immediately, in declaration order.
- **EM-13.** The report lists nodes in plan order, whatever the completion order. Only completion order, timings and the winners of `any`/`race` are non-deterministic.

## 4. Leaf processes

### 4.1 Launch

- **EM-14.** A leaf's program is resolved before launch: `exec` argv[0], or the shell binary for `script`, against `PATH` from Blokky's own environment, never the cwd. It is passed to the OS as an absolute path.
- **EM-15.** Every leaf runs in its own process group and session (Unix) or its own Job Object (Windows), so the leaf and everything it starts can be killed as a tree. Leaves have no controlling terminal.
- **EM-16.** A leaf's environment is Blokky's environment plus the `env` and `export` mappings of every enclosing scope, innermost last; `BASH_ENV` and `ENV` are then cleared.
- **EM-17.** A leaf's stdin is empty unless the plan sets `stdin`. Blokky never forwards its own stdin and never prompts.

### 4.2 Output

- **EM-18.** stdout and stderr are read concurrently, into bounded tail buffers (last 50 lines, at most 4 KiB per stream) and into the leaf's log files (capped by `max_log_bytes` and the per-run cap). Pipes are always drained, even after a log cap is reached, so a leaf never blocks on a full pipe.
- **EM-19.** With `stderr: merge`, both streams share one pipe and their interleaving is kept.

### 4.3 Completion

- **EM-20.** A leaf **completes when its direct child process exits**. Blokky then keeps reading its pipes for at most `drain_timeout` (default 2s) and closes them; if a descendant still held a pipe open, the report flags `descendants_held_output`.
- **EM-21.** At completion, the leaf's remaining process group, session or job is killed (graceful, then forced), unless the leaf sets `keep_descendants: true`.
- **EM-22.** Every descendant of every leaf dies no later than the end of the run, including when Blokky itself is killed with SIGKILL (the lifeline). Processes that deliberately escape (double-fork daemons, Windows breakaway) are handled on a best-effort basis. *Mechanism: provisional — verify in spike #1.*
- **EM-23.** The leaf succeeds if its exit code is 0 or listed in `ok_exit`. A leaf killed by a signal (Unix) fails; the report gives `signal`. The report gives `exit_code` (an unsigned 32-bit value on Windows) and, if Blokky killed it, `killed_by`.
- **EM-24.** Captures are evaluated after completion and bound only if the leaf succeeded ([variables.md](variables.md)).

## 5. Time limits

All limits use a monotonic clock.

| Limit | Applies to | Default | Error |
|---|---|---|---|
| `timeout` | a node, total | none | `BK_TIMEOUT_TOTAL` |
| `attempt_timeout` | one attempt or iteration (body only) | none | `BK_TIMEOUT_ATTEMPT` |
| `defaults.leaf_timeout` | each leaf and probe without its own `timeout` | none | `BK_TIMEOUT_TOTAL` |
| probe `timeout` | one probe | `probe_timeout` (30s), or `leaf_timeout` if smaller | condition error (unless `timeout_result`) |
| `finally_timeout` | a node's `finally` list | 5m | attached to the node's error |
| run budget | the whole run | 1m50s (fallback) | `BK_BUDGET_EXCEEDED` (exit 8) |

- **EM-25.** Nested limits combine: the effective limit at any point is the earliest deadline of all enclosing limits.
- **EM-26.** **When a limit fires**, Blokky sends the graceful signal to every process tree under that limit (SIGTERM on Unix; CTRL_BREAK on Windows when the leaf has a console, otherwise none), waits up to the **grace period** (default 5s), then force-kills (SIGKILL; `TerminateJobObject`). The grace period comes **after** the limit, not inside it ([ADR 0003](../adr/0003-execution-defaults.md), Q-k).
- **EM-27.** The node whose own limit fired is `timed_out`; its error code is always present, and leaves under it carry `killed_by: timeout` or `attempt_timeout`.
- **EM-28.** `sleep` and `every` waits end immediately when their node is cancelled or a limit fires.

## 6. Cancellation

A node is **cancelled** when something outside it stops it:

- a failing sibling under `fail_fast: true` (`do`, `all`, `for`);
- a decided `any` (a sibling succeeded) or `race` (*later*; a sibling completed);
- an ancestor's `timeout` or `attempt_timeout`;
- the run budget, or shutdown mode.

Rules:

- **EM-29.** Cancellation propagates down: every running descendant is cancelled; nodes that haven't started never start.
- **EM-30.** Cancelled processes get the graceful signal, then the forced kill after the grace period (EM-26).
- **EM-31.** `finally` of a cancelled node still runs, under `finally_timeout`, clamped by the cleanup deadline in budget and shutdown mode (§7).
- **EM-32.** **Joins confirm.** An `all`, `any` or `race` completes only after its cancelled children are confirmed: each direct child reaped and KILL sent to its group, session or job. Confirmation waits at most the grace period plus a fixed **reap timeout of 5s**. Anything still alive then is listed under `survivors` in the report, and the join completes anyway.
- **EM-33.** A cancelled node never retries and never starts another iteration.

## 7. Run budget, cleanup deadline and shutdown

### 7.1 Run budget

- **EM-34.** The run budget is the smallest of the explicit sources (config, `BLOKKY_MAX_DURATION`, `--max-duration`, and the remaining budget inherited by a nested run); with no explicit source it is the fallback 1m50s (blokky-cli ADR 0002).
- **EM-35.** At **budget − `cleanup_reserve`** (default 30s), Blokky enters **budget mode**: it cancels every running node, runs `finally` lists, writes the report and exits with 8. Leaves killed this way carry `killed_by: budget`.
- **EM-36.** `ignore_errors` never hides a budget kill, a shutdown or an ancestor's cancellation.
- **EM-54.** **Short budgets run without a reserve.** If the run budget is at or below `cleanup_reserve`, the effective reserve is zero: budget mode starts at the budget minus the report slice (EM-38), so cleanup gets no time — grace periods and `finally` are cut to zero and processes are force-killed — and the run ends at its budget. Blokky warns on stderr at run start ([ADR 0010](../adr/0010-variables-details.md)).

### 7.2 Single cleanup deadline

- **EM-37.** Entering budget, cancel-all or shutdown mode sets one **cleanup deadline**: the end of the budget (budget mode) or now + `cleanup_reserve` (shutdown).
- **EM-38.** From then on, every sub-timer (grace period, `finally_timeout`, `drain_timeout`, reap timeout) is clamped to `min(own, deadline − report slice)`, where the **report slice** is a fixed 2s kept for writing the report.

### 7.3 Shutdown mode

- **EM-39.** SIGINT, SIGTERM and SIGHUP (Unix) and console control events (Windows) put Blokky into **shutdown mode**: cancel all nodes, run `finally`, write a partial report, exit with 128 + the signal number (130 for SIGINT and for Ctrl-C/Ctrl-Break on Windows). Leaves killed this way carry `killed_by: shutdown`.
- **EM-40.** A **second** interrupt skips the remaining `finally` work and force-kills everything; the report is still written.
- **EM-41.** Leaves run in their own sessions, so a Ctrl-C in Blokky's terminal reaches only Blokky; Blokky then stops the leaves itself.
- **EM-42.** If stdout is closed (`blokky run … | head`), the report is written to the run dir only and the exit code is unchanged.

## 8. Status

### 8.1 Node statuses

| Status | Meaning |
|---|---|
| `succeeded` | The node finished without failing. |
| `failed` | The node failed. With `ignore_errors: true` it also carries `ignored: true`. |
| `skipped` | The node didn't start: its `when` was false (`skip_reason: condition`), or it was never reached because its parent ended early (`skip_reason: not_reached`). |
| `timed_out` | The node's **own** `timeout` or `attempt_timeout` fired. |
| `cancelled` | The node was running and was stopped from outside (§6). |

### 8.2 Propagation

([ADR 0009](../adr/0009-status-propagation.md))

- **EM-43.** A node is `timed_out` only if its own limit fired, and `cancelled` only if it was stopped from outside. A parent never inherits these statuses from a child: a parent whose child timed out or was cancelled is `failed` (or `cancelled`/`timed_out` for its own reasons), with the child's error as a cause.
- **EM-44.** A `do`, `all` or `any` whose children were **all skipped** is `succeeded`, and its `finally` runs.
- **EM-45.** `do` succeeds if no child failed (ignored failures don't count). `all` likewise. `any` succeeds if one child succeeded, or if no child failed (all skipped); it fails if no child succeeded and at least one failed.
- **EM-46.** A child that failed with `ignore_errors: true` is **not a success**: it doesn't fail its parent, but it doesn't win an `any` either; `any` goes on to the next alternative, and if none succeeds, the ignored failures are among its causes.
- **EM-47.** A condition error in `when` fails the node, and `ignore_errors` on that node applies to it. Since `when` is the first layer, no lock, tempdir or `finally` is involved.
- **EM-48.** `if` takes the status of the branch it ran; with a false condition and no `else`, it succeeds.
- **EM-49.** The children of an `all` stopped by a failing child are `cancelled` (running) or `skipped` with `not_reached` (unstarted), and the `all` fails with the first failure as its error.

### 8.3 Run status and exit code

- **EM-50.** The run's status is derived from the root node and the run mode: `succeeded` (the root succeeded, or was skipped by its `when`, exit 0); `failed` (exit 1); `budget_exceeded` (exit 8); `interrupted` (exit 128+N). The full exit-code table is in blokky-cli `cli.md`.

### 8.4 Error precedence

- **EM-51.** If a node's body fails and its `finally` also fails, the body error is primary and the `finally` error is attached. A failing `finally` fails an otherwise successful node.
- **EM-52.** When several children fail (`do` with `fail_fast: false`, `all`), the first failure in plan order is the primary error; the others are attached as causes. An `any` whose children all failed fails with `BK_ANY_ALL_FAILED` and every child error as a cause, in plan order.
- **EM-53.** Repetition errors (`BK_RETRIES_EXHAUSTED`, `BK_LOOP_MAX_REACHED`, `BK_TIMEOUT_TOTAL`) nest the last attempt's error.

## 9. Worked example: a cancellation timeline

```yaml
blokky: 0.1
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
| 31s | `finally` succeeds. The root is `failed` (its own timeout didn't fire). The report is written; exit 1. |

With a run budget of 1m50s and `cleanup_reserve` 30s, budget mode would start at 1m20s, after this run ends, so the budget plays no part here. A budget at or below `cleanup_reserve` runs without a reserve (EM-54).

## 10. Conformance

Every rule `EM-n` above has at least one conformance case in `conformance/cases/` that cites it. Timing rules are tested with the virtual clock where possible and with the tolerances in `conformance/README.md` otherwise.
