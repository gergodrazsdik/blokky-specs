# Reference

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is **normative for semantics**: what every node kind, leaf option and modifier does, and which combinations are valid. The plan schema (`schema/blokky.schema.json`) is normative for structure; §8 lists the rules the schema can't express. How fields are written (grammars, literal vs reference, pitfalls) is in [syntax.md](syntax.md); terms are in the [glossary](glossary.md). Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions).

Other files define the details this reference points to:

- [execution-model.md](execution-model.md): modifier order, start order, cancellation timeline, status propagation, process semantics;
- [variables.md](variables.md): names, scopes, captures, inputs, outputs, secrets;
- [conditions.md](conditions.md): subjects, operators, composites, probes, condition errors;
- [shells.md](shells.md): `exec` splitting, the shell invocation table, executable resolution;
- [containers.md](containers.md): `container`;
- [errors.md](errors.md): the `BK_` code catalogue.

Every feature described here belongs to the language 1.0. An implementation that doesn't support a feature yet rejects every plan that uses it with `BK_PLAN_NOT_SUPPORTED` before anything runs ([errors.md](errors.md)).

## 1. Node anatomy

A node is a YAML mapping with:

- **exactly one kind key** (§2). A node with no kind or with two kinds is a plan error;
- optional **companion fields** of its kind (`then`, `shell`, `concurrency`, …);
- optional **leaf options** (§3), on `exec` and `script` nodes only;
- optional **modifiers** (§4), subject to the validity matrix (§7).

**Body fields** (`do`, `then`, `else`, `finally`, `all`, `any`, `race`) hold lists of nodes and nothing else. A "block" such as a timeout block or a tempdir block is a `do` node with modifiers:

```yaml
- name: build in a scratch dir
  tempdir: { as: WORK }
  timeout: 10m
  do:
    - exec: [git, clone, --depth, '1', https://github.com/example/app.git, .]
    - exec: [make]
```

**Path ids.** Every node has a path id derived from its position: the root is `/`; a node in a body field is its parent's id plus `/<field>/<index>` (0-based), for example `/do/2`, `/do/2/all/0`, `/do/3/then/1`, `/finally/0`. Nodes inside loop bodies keep their plan path id; the run result tells iterations apart by their index ([results.md](results.md)).

Modifiers apply in a fixed order, outermost first: `when` → `timeout` → `lock` → `tempdir` → `cwd` → `env` → `container` → `services` → `finally` → repetition → `attempt_timeout` → kind ([execution-model.md](execution-model.md)).

## 2. Node kinds

| Kind | Summary |
|---|---|
| `exec` | Run a program without a shell. |
| `script` | Run shell text with a shell. |
| `do` | Run children in sequence. |
| `all` | Run children in parallel; all must succeed. |
| `any` | First success wins; an ordered fallback by default. |
| `race` | First completion decides. |
| `if` | Two-way branch on a condition. |
| `sleep` | Wait for a duration. |
| `log` | Record a message. |
| `fail` | Fail with a message and code. |
| `assert` | Fail unless a condition holds. |
| `set` | Bind variables. |
| `return` | End the enclosing sequence early, successfully. |

### 2.1 `exec`

Runs one program directly, without a shell.

- **Array form:** `exec: [prog, arg, { var: X }]`. Element 0 MUST be a literal; other elements are literals or `{ var: X }`, each becoming exactly one argument. Canonical when an argument is a variable or needs quoting.
- **String form** (canonical for a static argv that needs no quoting, SY-97): `exec: dotnet build -c Release` is split into argv with the rules in [shells.md](shells.md): whitespace, single and double quotes and backslash only; no expansion, globbing or operators. Unquoted shell metacharacters, and `$` or backticks outside single quotes, are plan errors that point to the array form or `script`.
- argv[0] is resolved against `PATH` from Blokky's own environment (never the cwd); the resolved absolute path is part of the run result. A program that can't be found fails the node with a spawn error.
- A literal argv[0] ending in `.bat` or `.cmd` (case-insensitive) is a plan error, and on Windows a bare name is never resolved to one (cmd.exe would re-parse the arguments; SH-10, SH-27); the message suggests a PowerShell `script`.
- The node succeeds if the process exits with 0 or a code listed in `ok_exit`.

### 2.2 `script`

Runs shell text with a shell.

```yaml
- name: test and keep a log
  script: |
    npm test 2>&1 | tee test.log
  shell: bash
```

- The text is written to a script file (readable only by the run's user) and passed to the shell as a file, with the invocation and prologue from [shells.md](shells.md) (bash: `-o pipefail`; PowerShell: `$ErrorActionPreference = 'Stop'`; sh: none).
- **Companion `shell`:** `bash`, `sh`, `pwsh`, `powershell`, `zsh`. Without `shell`, the shell comes from `defaults.shell`, then the implementation's configuration, then detection (bash → sh on Unix, pwsh → powershell on Windows).
- A reached `script` whose shell isn't supported on the current OS fails the node; statically false `host:` branches are pruned first.
- The text is executed as written; it never interpolates `${…}`. Plan variables reach it only through `env:` and `export:`.
- Success: exit 0 or a code in `ok_exit`.

### 2.3 `do`

Runs its children in order.

- **Companion `fail_fast`** (boolean, default `true`). With `true`, the first failing child fails the `do` and the remaining children don't start. With `false`, the remaining children still run, and the `do` fails at the end; the first failure in plan order is the primary error and the others are attached as causes.
- A capture of a child is visible to later siblings and after the `do` ([variables.md](variables.md)).

### 2.4 `all`

Runs its children in parallel; succeeds when all succeed.

- **Companion `concurrency`** (integer ≥ 1). Default: all children at once. An implementation MAY cap the effective concurrency of a node (for blokky-cli: `max_concurrency`, default 16); a cap reduces parallelism but never changes start order or results. Children start in declaration order; with a limit, the next child starts when a slot frees.
- **Companion `fail_fast`** (boolean, default `true`). With `true`, the first failure cancels the running children, prevents unstarted ones from starting, and fails the `all` once the cancelled children are confirmed dead. With `false`, all children run to completion and the `all` fails if any failed; errors are attached as with `do`.
- Two children MUST NOT bind the same variable name anywhere in their subtrees (RF-8).

### 2.5 `any`

Succeeds as soon as one child succeeds; fails only when all fail.

- **Companion `concurrency`** (integer ≥ 1, default **1**, capped as for `all`). With 1, `any` is an ordered fallback: try the first child, and only if it fails (or is skipped by its `when`), the next. With N > 1, up to N alternatives run at once, started in declaration order.
- When a child succeeds, running children are cancelled and unstarted ones never start.
- Only the winning child's captures are bound; different children MAY capture the same name (never an input's name).
- **All children fail:** the node fails with `BK_ANY_ALL_FAILED`; every child's error is attached as a cause, in plan order ([ADR 0003](../adr/0003-execution-defaults.md)).
- `fail_fast` is not valid on `any` (except inside `for:`).

### 2.6 `race`

Starts all children at once, in declaration order; the **first child to complete** decides the node's outcome, and the others are cancelled (and confirmed, EM-32). `concurrency` and `fail_fast` are not valid on `race`, except inside `for:`.

```yaml
- name: tests, unless the log shows OOM
  race:
    - exec: [dotnet, test]
    - name: OOM watchdog
      do:
        - name: wait for OOM in the log
          exec: [grep, -q, OutOfMemory, test.log]
          ok_exit: [1, 2]                  # no match yet, or no log yet
          until: { result: exit, equals: '0' }
          every: 5s
          timeout: 30m
        - fail: "test run hit OOM"
          code: OOM
```

(`until` checks its condition after each *successful* iteration, so the polling leaf must succeed while there is no match; `ok_exit` does that.)

- A child skipped by its `when` doesn't take part. A race whose children were all skipped succeeds.
- The deciding child's outcome is the race's: a success (or a failure hidden by `ignore_errors`) makes it succeed; a failure makes it fail with that child's error.
- Only the deciding child's captures are bound; different children MAY capture the same name (never an input's name). If the decider failed, nothing is bound ([ADR 0014](../adr/0014-remaining-features.md)).

### 2.7 `if`

```yaml
- if: { path: package-lock.json, exists: true }
  then:
    - exec: [npm, ci]
  else:
    - exec: [npm, install]
```

- `if:` takes a condition ([conditions.md](conditions.md)). **Companions:** `then` (required, list of nodes) and `else` (optional, list of nodes). An else-if is an `if` node inside `else`.
- The condition is evaluated once, in the node's own scope (after its `cwd`, `env` and other scoping modifiers). True runs `then`, false runs `else` (or nothing). A condition error fails the node.
- The node's status is that of the branch that ran; with no `else` and a false condition, the node succeeds. The nodes of the branch that didn't run are in the run result as `skipped` with skip reason `not_taken` ([ADR 0022](../adr/0022-wave-b-gaps.md)), or `pruned` when a `host:` condition decided the branch statically (CO-7).
- A branch runs its nodes in order and stops at the first failure, like a `do` with `fail_fast: true`. Implementations SHOULD suggest `when` for an `if` without `else`.

### 2.8 `sleep`

`sleep: 30s` waits for the duration (`0s` allowed). The wait ends immediately on cancellation. No process is started. Only `name` and `when` are valid on it (§7); for a conditional delay, put `when` on the `sleep`.

### 2.9 `log`

`log: "Watching run ${RUN_ID}"` records a message.

- **Companion `level`:** `debug`, `info` (default) or `warn`.
- The message is a display string (`${X}` interpolation, secrets masked). It is part of the run result ([results.md](results.md)); where an implementation also shows it (for example on stderr) is up to the implementation. No process is started. `log` replaces `echo` leaves.

### 2.10 `fail`

`fail: "No release tag on ${BRANCH}"` fails the node.

- **Companion `code`:** a user error code (default `BK_FAIL`).
- The message is a display string. An enclosing `retry: true` doesn't retry a `fail`; only a `retry:` condition matching its code does (§5.5).

### 2.11 `assert`

```yaml
- assert: { var: RUN_ID, matches: '^\d+$' }
  message: "No CI run found for branch ${BRANCH}"
  code: CI_RUN_NOT_FOUND
```

- `assert:` takes a condition. If it is true, the node succeeds; if false, the node fails with `code` (default `BK_ASSERT`) and `message`.
- **Companions:** `message` (display string, optional; the default names the condition) and `code` (optional).
- **A condition error** fails the node with the built-in condition-error code, not with `code`; the assertion's `message` and `code` are attached as context ([ADR 0002](../adr/0002-language-core.md), Q-n).

### 2.12 `set`

```yaml
- if: { var: ENVIRONMENT, equals: production }
  then:
    - set: { REPLICAS: '3', HOST: example.com }
  else:
    - set: { REPLICAS: '1', HOST: staging.example.com }
- set:
    URL: https://${HOST}/healthz
- exec: [curl, -fsS, { var: URL }]
```

- `set:` takes a mapping of variable names to values and binds each, in order (a later entry may use an earlier one). It starts no process and always succeeds unless a value can't be resolved. Only `name` and `when` are valid on it (§7); a conditional `set` is `when` on the `set`, and a value that may be missing is guarded with `when: { env: NAME, defined: true }` or a `set` in both branches of an `if`.
- **Values:** a literal; a whole-value reference (`{ var: X }`, `{ from_env: NAME }`, each optionally `secret: true`); or a **template**, a string with `${X}` placeholders and the display-string syntax (`$${` escapes). Templates are allowed only in `set` and `vars`; every executed argument stays a literal or one whole variable. There are no functions.
- An undefined variable in a template or reference fails the node (`BK_UNDEFINED_VARIABLE`; `BK_FROM_ENV_UNSET` for `from_env`). A value built from any secret part is secret.
- **Scope:** like a capture. Variables are single-assignment: setting a bound name is an error, and a name bound in every branch of an `if` is defined after it ([variables.md §6](variables.md#6-scope-and-binding), [ADR 0015](../adr/0015-set-and-vars.md)).

### 2.13 `return`

```yaml
do:
  - exec: [git, diff, --name-only, origin/main...HEAD]
    capture: CHANGED
  - when: { var: CHANGED, empty: true }
    return: "Nothing changed; nothing to lint"
  - name: lint ${CHANGED}
    exec: [./lint.sh]
```

`return: "message"` ends the **nearest enclosing sequence** successfully ([ADR 0017](../adr/0017-review-features.md)):

- **The sequence** is the nearest enclosing `do` list: the root's or a `do` node's, the body of a loop (where `return` ends the current iteration, like `continue`, and the loop goes on), or a `finally` list. `then` and `else` are transparent: a `return` in a branch ends the sequence that contains the `if`.
- The `return` node succeeds, and the sequence's remaining nodes are `skipped` with skip reason `returned`. The sequence's node then completes normally: its `finally` runs, and a loop goes on to its next iteration or condition check.
- The message is a display string, recorded like a `log` message at level `info`.
- A `return` whose nearest sequence would be reached through an `all`, `any` or `race` is a plan error: those groups have no order to end early. So is a `return` with no enclosing sequence at all (a root `return`, or one under a root `if` or `all`).
- A `return` without `when` that isn't inside a `then` or `else` gets a warning, because the nodes after it never run.
- There is no `break`: a loop ends through its own condition, `max` or source.
- Only `name` and `when` are valid on it (§7).

## 3. Leaf options

Leaf options are node-level siblings of `exec` or `script`; on any other kind they are plan errors. A mapping given as the value of `exec:` or `script:` (`exec: { cmd: …, timeout: 5m }`) is a plan error whose fix-it moves the options to the node.

| Option | Default | Meaning |
|---|---|---|
| `stdin` | empty | The leaf's standard input (below). |
| `ok_exit` | none | Extra exit codes that count as success. |
| `stderr` | separate | `merge` sends stderr into the stdout stream. |
| `encoding` | `utf-8` | How output is decoded for tails, captures and conditions. |
| `keep_descendants` | `false` | Don't kill the leaf's remaining processes at leaf completion (`true`), or at all (`detach`). |
| `capture` | — | Bind stdout (or JSON fields of it) to variables. |
| `capture_file` | — | Write stdout to a runtime-owned file and bind its path. |
| `secret` | `false` | Mark all captures of this node as secret. |

- **`stdin`.** By default a leaf's stdin is empty (`/dev/null`, or `NUL` on Windows); leaves never read the terminal. `stdin: "text"` passes literal text; `stdin: { var: X }` passes a variable's value; `stdin: { file: P }` passes the content of host file `P` (literal or `{ var: X }`, relative to the node's cwd). Text and `{ var: X }` values are passed as UTF-8 bytes exactly, with no newline added; `{ file: P }` passes the file's bytes unchanged.
- **`ok_exit`.** A list of exit codes (0 to 4 294 967 295, SY-96); exit 0 always succeeds. On Windows, exit codes are unsigned 32-bit values.
- **`stderr: merge`.** Both streams go to one pipe, so their interleaving is kept; captures and `result: stdout` then include stderr text.
- **`encoding`.** `utf-8`, `utf-16le`, `utf-16be` or `latin1`. Invalid sequences become U+FFFD wherever output is shown as text; captures treat them as errors ([variables.md](variables.md)).
- **`keep_descendants`.** By default, when the leaf's direct child exits, its remaining process group, session or job is killed. With `true` they keep running until the run ends. With `detach` they are never stopped by the run, not even at its end: the way to start a daemon, like `nohup x &` in bash. Static views show `detach`, and the run result lists the processes left running (EM-22, [ADR 0017](../adr/0017-review-features.md)).
- How much of a leaf's output an implementation keeps is its own configuration, not part of the plan.
- **`capture`, `capture_file`, `secret`.** `capture: NAME` binds stdout with trailing CR/LF removed; `capture: { NUM: .number, STATE: .state }` binds JSON fields of stdout; `capture_file: NAME` binds the path of a file holding stdout. Over `max_capture_bytes` (1 MiB) or containing a NUL byte, a capture fails the node; it never truncates. Captures are bound only if the node succeeds. Binding and scope: [variables.md](variables.md).

## 4. Modifiers

| Modifier | Valid on | Summary |
|---|---|---|
| `name` | all | Display label. |
| `when` | all | Run only if a condition holds, else `skipped`. |
| `timeout` | all but `sleep`, `log`, `fail`, `set`, `return` | Total wall-clock limit. |
| `lock` | see §7 | Hold a named advisory lock. |
| `tempdir` | see §7 | Create a runtime-owned temp dir and make it the cwd. |
| `cwd` | see §7 | Working directory. |
| `env` | see §7 | Scoped environment variables. |
| `export` | see §7 | Export plan variables as environment variables. |
| `container` | see §7 | Run leaves in an ephemeral container. |
| `services` | see §7 | Background processes around the node. |
| `finally` | all but `sleep`, `log`, `fail`, `set`, `return` | Cleanup nodes, run once per node. |
| `ignore_errors` | all but `sleep`, `log`, `fail`, `set`, `return` | The node's failure doesn't fail its parent. |
| `retry`, `while`, `until`, `for` | see §7 | Repetition (§5). |
| `attempt_timeout` | with repetition | Per-attempt or per-iteration limit. |

### 4.1 `name`

A display string, rendered per attempt or iteration (`name: build ${PROJ}`). The run result keeps the raw template for the node and the rendered text for each attempt and iteration. `name` never affects execution and need not be unique; nodes are identified by path ids. Implementations SHOULD warn about identical static names among siblings.

### 4.2 `when`

A guard condition, evaluated **once, before anything else, in the parent's scope**. If it is false, the node is `skipped`: it takes no lock, creates no tempdir, starts nothing and runs no `finally`. A condition error fails the node. A `when` that uses relative paths or probes on a node that sets `cwd` or `container` gets the `when-scope` lint warning, because those apply only inside the node.

### 4.3 `timeout`

The node's **total** wall-clock limit, measured on a monotonic clock. It covers lock wait, tempdir creation, container and service startup, the body and every repetition, but not `finally` (which has its own limit). When it fires, running processes get the graceful signal, then the forced kill after the grace period (5s), and the node fails with `BK_TIMEOUT_TOTAL`, status `timed_out`; an attempt it interrupts is the last attempt, and its `BK_CANCELLED` is nested (EM-53). The grace period comes after the limit ([ADR 0003](../adr/0003-execution-defaults.md), Q-k). Nested limits combine as the minimum.

There is no implicit `timeout` on groups or the root; `defaults.leaf_timeout` sets one for leaves and probes only. On a leaf with `retry`, `while` or `until`, `defaults.leaf_timeout` limits each attempt or iteration, like an implicit `attempt_timeout`, not the whole loop (`BK_TIMEOUT_ATTEMPT`, `killed_by: attempt_timeout`); the node's own `timeout` always limits the whole node, repetition included ([ADR 0018](../adr/0018-review-semantics.md)). An implementation may also stop a whole run from outside ([execution-model.md §7](execution-model.md#7-external-stops)).

### 4.4 `lock`

`lock: NAME` or `lock: { name: NAME, wait: 2m }` holds an exclusive lock named `NAME` for the node's duration (including its `finally`), so runs that use the same lock take turns, and so do two nodes of the same run (EM-60). Waiters acquire it in no particular order.

```yaml
- name: deploy staging, one at a time
  lock: deploy-staging
  timeout: 20m
  exec: [./deploy.sh, staging]
```

- **Scope:** lock names form one namespace per OS user on the machine: the same name in any plan, repository or run of that user is the same lock. Locks of other users never interact, root included: a run under `sudo` and a run as the user don't exclude each other.
- **Waiting:** without `wait`, the node waits as long as its `timeout` (and any external stop) allows. `wait` bounds the waiting time (`0s`: try once). Giving up fails the node with `BK_LOCK_TIMEOUT`. Waiting time counts against the node's `timeout`, and the run result records it.
- **Release:** the lock is released when the node ends, and also when the run's process dies, so a crashed run never leaves a lock behind (implementations use OS advisory locks).
- **No nesting:** a node with `lock` MUST NOT have a descendant with `lock`, including in `finally` and `services` ([ADR 0005](../adr/0005-containers-become-locks.md)). Locks are exclusive only ([ADR 0014](../adr/0014-remaining-features.md)).

### 4.5 `tempdir`

`tempdir: true` or `tempdir: { as: WORK, prefix: build, remove: on_success }`.

- Creates a fresh directory (mode 0700, unpredictable name, optional `prefix`) under the per-user temp root, **once per node** (not per attempt; nest `retry` inside to get a fresh dir per attempt).
- The directory **becomes the node's cwd**. A relative `cwd` on the same node resolves inside it; an absolute `cwd` together with `tempdir` is a plan error.
- `as` binds the directory's absolute path to a variable visible inside the node.
- **`remove`:** `true` deletes the directory at node end, after `finally`; `on_success` deletes it only if the node succeeded, so a failure can be inspected. Removal never follows symbolic links. `false`, the default, keeps the directory, and removing it later is the implementation's business (for blokky-cli: `blokky clean`).
- `prefix` matches `^[A-Za-z0-9._-]{1,32}$`.

### 4.6 `cwd`

The working directory for the node and everything inside it: a literal path or `{ var: X }`. A relative path resolves against the parent's cwd (at the root: the invocation cwd), so paths are built by nesting. A cwd that doesn't exist or isn't a directory when the node starts fails the node (`BK_CWD_INVALID`). Under `container`, an absolute `cwd` that isn't under a mount is a path inside the container and is checked there, not on the host (CP-14).

### 4.7 `env` and `export`

```yaml
env:
  CONFIGURATION: Release
  RUN: { var: RUN_ID }
  GH_TOKEN: { from_env: GH_TOKEN, secret: true }
export: [BRANCH]
```

- `env` sets environment variables for every process in the node's scope, layered over the parent's environment. Values are literals, `{ var: X }` or `{ from_env: NAME }`, each optionally `secret: true`.
- `export` makes the listed plan variables environment variables of the same name.
- `env` MUST NOT set `PATH`, `BASH_ENV`, `ENV`, `SHELLOPTS` or `BASHOPTS`; `BASH_ENV` and `ENV` are cleared for every leaf. `export` MUST NOT name a reserved environment name ([variables.md](variables.md)); setting one deliberately needs an explicit `env` entry, which `leaves` flags as `exec_env_risk` when the name is execution-influencing.
- A name both in `env` and in `export` on the same node is a plan error. On Windows, names are compared case-insensitively.

### 4.8 `container`

`container: { image, mounts, env_pass }` runs the node's leaves in an ephemeral container started for the node and stops (not removes) afterwards. By default the cwd is mounted read-write at the same path. Full semantics: [containers.md](containers.md).

### 4.9 `services`

Background processes that live for the node's duration: a database, a dev server, a mock API.

```yaml
- name: integration tests
  services:
    - name: db
      exec: [postgres, -D, ./pgdata, -p, '5433']
      ready: { port: 5433, open: true }
    - name: api                       # starts after db is ready
      exec: [dotnet, run, --project, src/Api]
      env: { DB_PORT: '5433' }
      ready: { output: stdout, contains: 'Now listening' }
      ready_timeout: 1m
  exec: [dotnet, test, tests/Integration]
```

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Unique among the node's services (`^[a-z0-9][a-z0-9._-]{0,63}$`). |
| `exec` or `script` (+ `shell`) | yes | The process, as for leaves. |
| `env`, `export`, `cwd` | no | As for leaves; the service runs in the node's scope. |
| `ready` | yes | A condition polled until it holds ([conditions.md](conditions.md)); may use the service-only subjects `port` and `output`, and probes. |
| `ready_timeout` | no | How long readiness may take; default 30s, within the node's `timeout`. |
| `on_exit` | no | `fail` (default) or `ignore`: what happens if the service exits on its own after it was ready. |

- **Start:** services start one at a time, in list order; each starts after the previous one is ready. The node's body starts when every service is ready.
- **Readiness:** `ready:` is first checked right after the service process starts, then 250ms after the previous check ends. A service that exits before it is ready, or isn't ready within `ready_timeout`, fails the node (`BK_SERVICE_EXITED`, `BK_SERVICE_NOT_READY`); services already started are stopped, and the body and `finally` don't run: their nodes are `skipped` with `not_reached` (EM-63).
- **While the body runs:** a service with `on_exit: fail` that exits on its own cancels the body and fails the node with `BK_SERVICE_EXITED` (with the service name and exit code). With `on_exit: ignore`, the exit is recorded and the body continues. A service that exits after the body ended (for example during `finally`) is recorded, not a failure.
- **Stop:** after the node's `finally`, services are stopped in reverse list order, each as a whole process tree (graceful, then forced). An exit caused by stopping is not a failure.
- **Visibility:** services bind no variables. The run result lists the services that started, in list order, with each one's readiness time, measured from the node's start, and how it ended: `stopped` by the run, `exited` with its exit code (also before it was ready), or `never_ready` (not ready in time, or stopped by a timeout or cancellation during startup) ([results.md](results.md)). Services are processes the plan executes, like leaves, and are stoppable the same way (EM-15).

([ADR 0014](../adr/0014-remaining-features.md))

### 4.10 `finally`

A list of cleanup nodes that runs **once per node** (not per attempt or iteration) after the node's body ends, whether it succeeded, failed, timed out or was cancelled.

- **Companion `finally_timeout`** (duration, default 5m). `finally` runs under it even after the node's `timeout` fired; when the runtime stops the whole run, it may get less time ([execution-model.md §7](execution-model.md#7-external-stops)). When it fires, the running `finally` nodes are `cancelled`, their leaves with `killed_by: finally_timeout`, and the `finally` list fails with `BK_TIMEOUT_FINALLY` (EM-7, [ADR 0024](../adr/0024-wave-d-gaps.md)).
- A node skipped by `when` runs no `finally`.
- `finally` runs inside the node's tempdir, cwd, env, container and services, and sees what the body bound.
- **Errors:** a `finally` list runs every node even if one fails, like a `do` with `fail_fast: false`, so each cleanup step is tried; it fails with its first failure ([ADR 0022](../adr/0022-wave-b-gaps.md)). A failing `finally` fails an otherwise successful node. If the body failed too, the body error is primary and the `finally` error is attached.
- Captures under `finally` are visible only to later nodes in the same `finally` list ([ADR 0002](../adr/0002-language-core.md), Q-s).

### 4.11 `ignore_errors`

`ignore_errors: true`: if the node fails, its parent treats it as not failed. It covers every failure of the node itself, its own `timeout` and `attempt_timeout` included: the run result keeps the node's status (`failed` or `timed_out`) and adds `ignored: true`. It never hides an outer cancellation, an ancestor's timeout or an external stop. It isn't valid on the root (RF-33). A node whose failure is ignored binds no captures (use `ok_exit` when a capture should survive a known exit code).

### 4.12 `attempt_timeout`

A limit for each attempt (`retry`) or iteration (`while`, `until`, `for`), valid only together with a repetition modifier. It covers the body only: not the condition (probes have their own timeouts), not the `every` wait. When it fires, the attempt's processes are killed (graceful, then forced) and the attempt fails with `BK_TIMEOUT_ATTEMPT`.

## 5. Repetition

### 5.1 Common rules

- A node has **at most one** of `retry`, `while`, `until`, `for`. Combinations are written by nesting nodes.
- Repetition sits inside `finally` in the modifier order, so `finally`, `tempdir`, `cwd`, `env` and the scoping modifiers apply once around all attempts or iterations.
- The run result records the number of attempts or iterations, what ended them (`ended_by`, [results.md §3](results.md#3-nodes)), the last condition result, and per-iteration entries (rendered name, index, item).

### 5.2 Sibling fields

| Field | `retry` | `while` | `until` | `for` | Default |
|---|---|---|---|---|---|
| `max` (total attempts or iterations, integer ≥ 1) | yes | yes | yes | — | `retry`: 3; `while`/`until`: none (see §5.6) |
| `every` (duration, `0s` allowed) | yes | yes | yes | — | 1s |
| `attempt_timeout` | yes | yes | yes | yes | none |
| `backoff: { factor, max }` | yes | — | — | — | none (fixed delay) |
| `jitter` | yes | — | — | — | none |
| `on_body_failure: stop \| continue` | — | yes | yes | — | `while`: `stop`; `until`: `continue` |
| `index` (§5.8) | yes | yes | yes | — | none |
| `carry` (§5.8) | — | yes | yes | — | none |
| `collect` (§5.8) | — | yes | yes | yes | none |

Using a field where the table says "—" is a plan error. `for` takes its own options inside `for:` (§5.7); its index is `<AS>_INDEX`.

### 5.3 `every`, `backoff` and `jitter`

- **`every`** is the delay between the **end** of one attempt or iteration (including its condition check) and the **start** of the next. There is no delay before the first. In `while`, whose condition is checked before each iteration, the wait comes first, then the condition check, right before each iteration ([ADR 0024](../adr/0024-wave-d-gaps.md)). The default is 1s, so a loop never runs back to back by accident; `every: 0s` removes the delay. Waits end immediately on cancellation.
- **`backoff: { factor: F, max: D }`** (`retry` only) grows the delay: the delay before attempt n+1 is `every × F^(n−1)`, capped at `max`. `factor` is a decimal from 1 to 10 and required in the mapping; `max` is a duration, default 5m.
- **`jitter: J`** (`retry` only, decimal 0 < J ≤ 1) multiplies each delay by a random value in [1 − J, 1], drawn from a random source that implementations MAY make seedable, so tests can be reproducible.

### 5.4 `retry`

`retry: true` or `retry: <condition>`.

1. Run attempt 1.
2. If it succeeds, the node succeeds, and captures on the node are bound from it.
3. If it fails, decide whether to retry: with `retry: true`, by the table in §5.5; with a condition, by evaluating it against the failed attempt (the `result:` subject sees its `stdout`, `stderr`, `exit` and `error`; after an `attempt_timeout`, `error` is `BK_TIMEOUT_ATTEMPT`).
4. If no retry is warranted, the node fails with the attempt's error.
5. If attempts reached `max`, the node fails with `BK_RETRIES_EXHAUSTED`, with the last attempt's error nested. Its status is `failed`, even if the attempts timed out (EM-27).
6. Otherwise wait the delay (§5.3) and run the next attempt.

`on_body_failure` is not valid on `retry`.

### 5.5 What `retry: true` retries

This table summarizes the categories; [errors.md §5](errors.md#5-node-errors) gives the answer for every code.

| Failure of an attempt | Retried by `retry: true` | Retried by a `retry:` condition |
|---|---|---|
| Non-zero exit (not in `ok_exit`), killed by a signal | yes | if the condition holds |
| `BK_TIMEOUT_ATTEMPT` | yes | if the condition holds |
| Capture failure (missing JSON path, over the size limit, NUL byte) | yes | if the condition holds |
| `fail` or `assert` with a user code | no | if the condition matches the code |
| Condition error | no | if the condition matches the condition-error code |
| Spawn error (program not found, not executable) | no | if the condition matches the code |
| A descendant's own `timeout` inside the attempt (`BK_TIMEOUT_TOTAL`) | yes | if the condition holds |
| The retrying node's own `timeout`, an ancestor's limit, cancellation, external stops | never | never |

For a group node with `retry`, "attempt failed" means the group failed, and the group's error code is what the table and condition see. "Never" is decided by where a limit came from, not by its code: a `timeout` on a node inside the attempt ends only that attempt, while the retrying node's own `timeout` covers all attempts and ends the node ([ADR 0018](../adr/0018-review-semantics.md)).

### 5.6 `while` and `until`

- **Bounded loops:** `while` and `until` MUST have `max`, `timeout`, or both. An unbounded loop is a plan error.
- **`while: <condition>`** checks the condition **before** each iteration, after the `every` wait (§5.3). The first check sees only the enclosing scope; later checks also see the previous iteration's captures. False ends the loop successfully, so a `while` that is false at the first check succeeds with zero iterations (`ended_by: condition`).
- **`until: <condition>`** checks the condition **after** each successful iteration; true ends the loop successfully. Polling is `until` with a `result:` condition.
- **Body failure** (including `BK_TIMEOUT_ATTEMPT`): with `on_body_failure: stop`, the node fails with the body's error. With `continue`, the iteration counts as "not done yet": no condition is checked, and the loop goes on to the next iteration after the delay. In `until`, a condition error from the `result:` subject (a response that isn't the expected JSON yet) counts as a body failure too (CO-40).
- **Reaching `max`** without the condition ending the loop fails the node with `BK_LOOP_MAX_REACHED`, with the last iteration's error or condition error (if any) nested. Reaching `timeout` fails with `BK_TIMEOUT_TOTAL` (EM-53). A loop whose iterations hit `attempt_timeout` and that then reaches `max` is `failed`, not `timed_out` (EM-27).
- Captures on the repeating node itself are bound from the terminating iteration; captures in a loop body are scoped to the loop ([variables.md](variables.md)). Values pass from one iteration to the next only through `carry`, and leave the loop only through `collect` (§5.8).

### 5.7 `for`

All `for` options live inside the `for:` mapping:

```yaml
- name: build ${PROJ}
  for: { glob: "src/**/*.csproj", as: PROJ, concurrency: 4 }
  exec: [dotnet, build, { var: PROJ }, -c, Release]
```

**Sources** (exactly one):

| Source | Items |
|---|---|
| `each: [a, b, c]` | The listed strings (non-empty list). |
| `count: N` | `0` … `N−1`; `count: 0` runs zero iterations and succeeds. |
| `glob: "pattern"` | Matching host paths, expanded by Blokky (below). |
| `items: { var: X, json: .path }` | Elements of the JSON array that the path (default `.`) selects in a variable; each converted to a string as in field captures ([variables.md](variables.md), VA-23). A value that isn't JSON, or a path that doesn't select an array, fails the node. |
| `lines: { var: X }` | Lines of a variable: split on LF, a CR before an LF removed; lines that are empty or only whitespace are dropped unless `keep_blank: true`. Line content is otherwise kept exactly. |
| `matrix: { OS: [..], ARCH: [..] }` | The Cartesian product, in key order with the first key varying slowest; binds each key as a variable. There is no `exclude`/`include`: skip combinations with a `when` inside the body. |

**Options:**

- A source with no items (`each` can't be empty; `count: 0`; an `items` array or `lines` value with no entries) runs zero iterations and succeeds; only `glob` fails on zero matches unless `allow_empty: true`.
- `as` (variable name): **required** for every source except `matrix`, where it is forbidden. It binds the item; `<AS>_INDEX` binds the **0-based** index. For `matrix`, the index is `MATRIX_INDEX` and the result's item is an object.
- `concurrency` (integer ≥ 1, default 1, capped by `max_concurrency`): above 1 the loop is a fan-out; iterations start in item order.
- `fail_fast` (boolean, default `true`): as for `all`. A loop stopped by `fail_fast` ends with `ended_by: failure`; one that ran all its items ends with `ended_by: items`, even if some failed ([results.md §3](results.md#3-nodes)).
- `allow_empty` (boolean, default `false`, `glob` only): zero matches succeed with zero iterations instead of failing.
- `max_items` (integer, default 1000, every source): more items (for `matrix`, more combinations) fail the node with `BK_ITEMS_TOO_MANY` before the first iteration; items are never truncated.
- `fields` (`items` only): `{ NAME: .path, … }` binds a variable per field from each item, with the JSON-path subset and conversion of field captures. A path that doesn't resolve for an item fails that iteration with `BK_CAPTURE_PATH`.
- `keep_blank` (boolean, default `false`, `lines` only): keep empty and whitespace-only lines as items.

```yaml
- exec: [gh, pr, list, --json, 'number,headRefName']
  capture: PRS
- name: check PR ${NUM}
  for:
    items: { var: PRS }
    as: PR
    fields: { NUM: .number, BRANCH: .headRefName }
    concurrency: 4
  exec: [gh, pr, checks, { var: NUM }]
```

**Glob rules:** patterns use the glob grammar of [syntax.md §6.9](syntax.md#69-glob-patterns), matched ordinally and case-sensitively on every OS; files and directories match (SY-99); ordinal sort of the matches; no dot-entries unless the pattern segment starts with `.` (SY-100); symbolic links match as entries but are never followed into (SY-101); `/` separators in item values; a `..` segment is a plan error (SY-102); zero matches is an error unless `allow_empty: true`. Patterns are host paths relative to the node's cwd.

**Iterations** never publish captures to the enclosing scope (only through `collect`, §5.8). A for-loop's iteration count and items are in the run result. Put `--` before item values and inputs used as `exec` arguments where the program supports it (§9).

### 5.8 Loop variables: `index`, `carry` and `collect`

These sibling fields bind variables around a loop's iterations ([ADR 0017](../adr/0017-review-features.md)). Each name is still bound once per iteration, so single assignment holds ([variables.md §6](variables.md#6-scope-and-binding)).

```yaml
- name: fetch all issues
  until: { var: NEXT, empty: true }
  carry: { CURSOR: NEXT }          # '' in iteration 1, then the previous NEXT
  collect: { PAGE: PAGES }         # every PAGE, as a list, after the loop
  index: { as: PAGE_NO, start: 1 }
  max: 100
  timeout: 5m
  do:
    - log: "page ${PAGE_NO}"
    - exec: [./fetch-issues, --cursor, { var: CURSOR }]
      capture:
        PAGE: { json: .items }
        NEXT: { json: .next_cursor }
```

- **`index`** (`retry`, `while`, `until`): `index: NAME` binds the attempt or iteration number, 0-based; `{ as: NAME, start: N }` starts at `N` (an integer). It is visible in the body and in the node's own condition, and isn't published. `for` binds its index as `<AS>_INDEX` instead.
- **`carry`** (`while`, `until`): `carry: { NAME: CAPTURE }` binds `NAME` at the start of each iteration: `''` in the first, then the value `CAPTURE` had at the end of the previous iteration. The long form `{ NAME: { from: CAPTURE, initial: VALUE } }` sets another first value (a literal). `CAPTURE` is a capture bound in the body (or by the node's own `capture`); if the previous iteration didn't bind it (a failed body under `on_body_failure: continue`, or a `return` first), `NAME` keeps its previous value, so a failed page is fetched again. `NAME` is visible in the body and in the condition, isn't published, and is secret if `CAPTURE` is.
- **`collect`** (`for`, `while`, `until`): `collect: { CAPTURE: LISTVAR }` binds `LISTVAR`, after the loop, to a compact JSON array of each iteration's `CAPTURE` value (bound in that iteration by the node's own `capture`, when the node is a leaf, or by a node in its body), in item or iteration order, with `null` for iterations that failed, were skipped, were cancelled or didn't bind it (`["12 passed",null,"8 passed"]`). The list is bound **also when the loop fails**, so a summary in `finally`, after `ignore_errors` or in a `fail_fast: false` sequence can report what happened; this is an exception to captures binding only on success. Items are strings: a JSON capture is collected as its JSON text. The list can feed a `for: { items }`, a `json:` condition or `outputs`.

## 6. Plan-level keys

`blokky`, `inputs`, `vars`, `outputs` and `defaults` are allowed only at the root; see [syntax.md §4](syntax.md#4-the-plan-document) and [variables.md](variables.md). The root mapping is also the root node: it holds exactly one kind and may carry modifiers.

## 7. Validity matrix

Which modifiers and companion groups each kind accepts. ✓ = valid; — = plan error. `name` and `when` are valid on every kind. `timeout`, `finally` (with `finally_timeout`) and `ignore_errors` are valid on every kind except `sleep`, `log`, `fail`, `set` and `return`, where they would mean nothing: those nodes start no process, have nothing to clean up and can't fail in a way worth ignoring (a `sleep` ends early only by cancellation, which `ignore_errors` never hides; ignoring a `fail` is a no-op) ([ADR 0015](../adr/0015-set-and-vars.md)). Neither group is repeated below.

| Kind | Scope (`cwd`, `env`, `export`, `tempdir`, `lock`, `container`, `services`) | `retry`, `while`, `until` | `for` | `attempt_timeout` | Leaf options (§3) | `concurrency` | `fail_fast` |
|---|---|---|---|---|---|---|---|
| `exec` | ✓ | ✓ | ✓ | with repetition | ✓ | `for` only | `for` only |
| `script` | ✓ | ✓ | ✓ | with repetition | ✓ | `for` only | `for` only |
| `do` | ✓ | ✓ | ✓ | with repetition | — | `for` only | ✓ |
| `all` | ✓ | ✓ | ✓ | with repetition | — | ✓ | ✓ |
| `any` | ✓ | ✓ | ✓ | with repetition | — | ✓ | `for` only |
| `race` | ✓ | ✓ | ✓ | with repetition | — | `for` only | `for` only |
| `if` | ✓ | ✓ | ✓ | with repetition | — | `for` only | `for` only |
| `assert` | ✓ | ✓ | ✓ | with repetition | — | `for` only | `for` only |
| `log` | — | — | ✓ | — | — | `for` only | `for` only |
| `sleep` | — | — | — | — | — | — | — |
| `fail` | — | — | — | — | — | — | — |
| `set` | — | — | — | — | — | — | — |
| `return` | — | — | — | — | — | — | — |

"`for` only" means the field is valid only inside the `for:` mapping of that node. On a node that has `for`, node-level `concurrency` and `fail_fast` are plan errors for every kind: they would apply to the inner group, not the loop. The loop's settings go in `for:`; an inner `all` or `any` with its own settings is written as a child node (RF-31). `index`, `carry` and `collect` are valid wherever the repetition they belong to is (§5.2, §5.8). Companion fields of a kind (`then`/`else`, `shell`, `level`, `message`, `code`) are valid only on their kind. `collect` with `for` on `log` is valid in this table but can never be used: a `log` binds no capture, so RF-30 always rejects it.

## 8. Rules beyond the schema

Implementations MUST enforce these as plan errors (unless noted), with `BK_PLAN_INVALID`, except RF-21 and RF-22, which are `BK_PLAN_VALUE`; a rule elsewhere that restates one of these is reported under its `RF-n` ID ([errors.md §4](errors.md#4-plan-errors)). Rules carry IDs (`RF-n`) for conformance cases and for `detail.rule`. The schema also enforces the ones marked *(schema)*, so an editor with the schema catches them before an implementation runs; implementations report them with the rule's ID either way.

- **RF-1.** Exactly one kind per node.
- **RF-2.** At most one repetition modifier per node.
- **RF-3.** The validity matrix (§7) and the per-repetition sibling table (§5.2). *(schema)*
- **RF-4.** `attempt_timeout` only with a repetition modifier. *(schema)*
- **RF-5.** `while` and `until` have `max` or `timeout` (or both). *(schema)*
- **RF-6.** Modifiers outside repetition (`when`, `timeout`, `lock`, `tempdir`, `cwd`, `env`, `container`, `services`) don't reference variables the node itself introduces (`as`, `tempdir.as`, `index`, `carry`, its own captures): "move it into the body".
- **RF-7.** Shadowing: no variable name is bound twice in nested scopes, including by `index` and `carry`; inputs collide with every other binding.
- **RF-8.** Two children of an `all` don't bind the same name anywhere in their subtrees, except names scoped to a loop iteration, which never reach the `all`'s scope.
- **RF-9.** Inputs and variables never reach literal fields; argv[0] of an `exec` array is a literal.
- **RF-10.** `env` doesn't set a forbidden key; `export` doesn't name a reserved environment name; no name is in both `env` and `export` on one node.
- **RF-11.** An absolute `cwd` is not combined with `tempdir` on one node.
- **RF-12.** Captures (`capture`, `capture_file`, `secret`) only on `exec` and `script` nodes. *(schema)*
- **RF-13.** The `result:` subject only in `until` and `retry` conditions; `result: stdout|stderr|exit` only when the node's kind is `exec` or `script`.
- **RF-14.** `not:` isn't wrapped around a simple condition that has a `not_*` form.
- **RF-15.** An `outputs` entry isn't bound only inside a loop body (unless gathered with `collect`).
- **RF-16.** Captures under `finally` aren't referenced outside that `finally` list.
- **RF-17.** No `lock` inside a `lock`.
- **RF-18.** `as` is present for scalar `for` sources and absent for `matrix`. *(schema)*
- **RF-19.** A secret marker is only on references, never on literals; a literal marked secret (SY-91) is reported under this rule, not as an unknown key.
- **RF-20.** An input's `default` satisfies its constraint; at most one of `in`/`matches`.
- **RF-21.** Empty lists only in fields that allow them (`mounts`).
- **RF-22.** A regex stays within the portable subset ([syntax.md §6.7](syntax.md#67-regular-expressions)).
- **RF-23.** A reference (`${X}`, `{ var: X }`, a `var:` subject, an `outputs` entry) names a variable that some binding can provide before it: a syntactic scope check over the plan. A reference with no possible binding is a plan error; whether a possible binding actually happened is checked at run time ([variables.md §6](variables.md#6-scope-and-binding)).
- **RF-24.** Service names are present and unique within a node.
- **RF-25.** `fields` only with `items`; `keep_blank` only with `lines`; `allow_empty` only with `glob`. *(schema)*
- **RF-26.** A name isn't bound twice: not by two sequential siblings, not by `set` for a bound name, not by `vars` for an input or another `vars` entry. Two sequential loops may bind the same loop variable, because each binds it in its own iteration scope.
- **RF-27.** Templates (`${…}` in executed values) appear only in `set` and `vars` values; `vars` values use only inputs, earlier `vars` and `from_env`.
- **RF-28.** `timeout`, `finally`, `finally_timeout` and `ignore_errors` are not used on `sleep`, `log`, `fail`, `set` or `return`. *(schema)*
- **RF-29.** A `return` has an enclosing sequence, and it is not reached through an `all`, `any` or `race` (§2.13).
- **RF-30.** `index` only with `retry`, `while` or `until`; `carry` only with `while` or `until`; `collect` only with `for`, `while` or `until`. `carry` and `collect` name a capture bound by the node or in its body; `index` and `carry` names follow the shadowing rules (RF-7).
- **RF-31.** Node-level `concurrency` and `fail_fast` don't appear on a node that has `for` (§7). *(schema)*
- **RF-32.** Companion fields only with their owner: `then`/`else` with `if` (and `if` has `then`), `shell` with `script`, `level` with `log`, `message` with `assert`, `code` with `fail` or `assert`, `finally_timeout` with `finally`. *(schema)*
- **RF-33.** `ignore_errors` isn't used on the root: there is no parent to hide the failure from. *(schema)*

## 9. Security considerations

- **Baseline.** Running a plan is equivalent to running the same commands in bash: Blokky grants no capability, bypasses no permission system and hides nothing that will run. The programs a plan can start, the shape of every argv and environment, and the source of every value are determinable from the plan, its inputs and the environment it starts with, before it runs; only captured values are known at run time ([ADR 0018](../adr/0018-review-semantics.md)), so implementations can show it for review (for blokky-cli: [`leaves`](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/leaves-and-validation.md)).
- **Allowing `blokky run`.** To a runner that matches command lines, `blokky run` is one command that runs arbitrary code. Allowing it without the implementation's approval mechanism (for blokky-cli: the hook or validator, which expand the plan into its leaves) allows everything the plan contains, exactly like allowing `bash`. What must be reviewed is the plan text.
- **Untrusted text.** Rendered display strings, captured values and recorded items in the run result can contain untrusted data (command output, API responses). They are display-sanitized (SY-98) and are never instructions.
- **Hygiene is not a control.** Lint, secret masking and display sanitization make plans cleaner and more reviewable; they don't decide what may run. Deciding is the job of controls outside the language: the agent runner's permission system and the implementation's approval mechanisms (for blokky-cli: the hook and validator).
- **Dynamic code.** A variable used as code (`sh -c` with a variable, `python -c`, `node -e`, `eval`, `iex`) is string interpolation into code, with the same injection risk as in bash, whether the value came from an input, a capture or a `set` template. The safe pattern is `script` with `export`. A variable used as code, execution-influencing environment variables, dynamic nested plans, dynamic stdin into an interpreter and a dynamic cwd are statically recognizable, so implementations can flag them for review.
- **Argument injection.** Item values, captures and inputs passed as `exec` arguments can start with `-`, which most programs read as an option. Put `--` before them where the program supports it, and constrain inputs with `matches` so they can't start with `-` (for example `'^[A-Za-z0-9._/][A-Za-z0-9._/-]*$'`). This is hygiene: it reduces mistakes, it doesn't decide what may run.
- **Secrets.** Masking doesn't follow derived values, and conditions on secrets act as oracles. Secrets come only by reference, so their values never appear in the plan or in a static view of it.
- **Probes** SHOULD be side-effect-free; they run as real processes in the node's scope.
- **Containers** are not a sandbox by default; mounting the engine socket or running privileged is equivalent to host root.
- **Users.** Every process runs as the user Blokky runs as; a plan that needs another user calls `sudo -n` or `doas -n` in a leaf, as in bash (CP-39).
- **Daemons.** `keep_descendants: detach` leaves processes running after the run, like `nohup x &` in bash; static views show it.
- **Resource bounds** (timeouts, caps, the concurrency cap) exist for predictability, not as security boundaries.
