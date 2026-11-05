# Reference

Status: **draft** (spec 0.1, not yet finalized)

This document is **normative for semantics**: what every node kind, leaf option and modifier does, and which combinations are valid. The plan schema (`schema/blokky.schema.json`) is normative for structure; §8 lists the rules the schema can't express. How fields are written (grammars, literal vs reference, pitfalls) is in [syntax.md](syntax.md); terms are in the [glossary](glossary.md). Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions).

Other files define the details this reference points to:

- [execution-model.md](execution-model.md): modifier order, start order, cancellation timeline, status propagation, process semantics;
- [variables.md](variables.md): names, scopes, captures, inputs, outputs, secrets;
- [conditions.md](conditions.md): subjects, operators, composites, probes, condition errors;
- [shells.md](shells.md): `exec` splitting, the shell invocation table, executable resolution;
- [containers-and-privilege.md](containers-and-privilege.md): `container` and `become` (*later*);
- [errors.md](errors.md): the `BK_` code catalogue.

Every feature carries a milestone tag: **v0.1** or ***later***. A later keyword is reserved: a v0.1 implementation rejects it with "not supported in this version".

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

Modifiers apply in a fixed order, outermost first: `when` → `timeout` → `lock` → `tempdir` → `cwd` → `env` → `container`/`become` → `services` → `finally` → repetition → `attempt_timeout` → kind ([execution-model.md](execution-model.md)).

## 2. Node kinds

| Kind | Milestone | Summary |
|---|---|---|
| `exec` | v0.1 | Run a program without a shell. |
| `script` | v0.1 | Run shell text with a shell. |
| `do` | v0.1 | Run children in sequence. |
| `all` | v0.1 | Run children in parallel; all must succeed. |
| `any` | v0.1 | First success wins; an ordered fallback by default. |
| `race` | *later* | First completion decides. |
| `if` | v0.1 | Two-way branch on a condition. |
| `sleep` | v0.1 | Wait for a duration. |
| `log` | v0.1 | Record a message. |
| `fail` | v0.1 | Fail with a message and code. |
| `assert` | v0.1 | Fail unless a condition holds. |

### 2.1 `exec` (v0.1)

Runs one program directly, without a shell.

- **Array form (canonical):** `exec: [prog, arg, { var: X }]`. Element 0 MUST be a literal; other elements are literals or `{ var: X }`, each becoming exactly one argument.
- **String form:** `exec: dotnet build -c Release` is split into argv with the rules in [shells.md](shells.md): whitespace, single and double quotes and backslash only; no expansion, globbing or operators. Unquoted shell metacharacters, and `$` or backticks outside single quotes, are plan errors that point to the array form or `script`.
- argv[0] is resolved against `PATH` from Blokky's own environment (never the cwd); the resolved absolute path is part of the run result. A program that can't be found fails the node with a spawn error.
- On Windows, `.bat` and `.cmd` targets are plan or run errors (cmd.exe re-parses them); the message suggests a PowerShell `script`.
- The node succeeds if the process exits with 0 or a code listed in `ok_exit`.

### 2.2 `script` (v0.1)

Runs shell text with a shell.

```yaml
- name: test and keep a log
  script: |
    npm test 2>&1 | tee test.log
  shell: bash
```

- The text is written to a script file (readable only by the run's user) and passed to the shell as a file, with the invocation and prologue from [shells.md](shells.md) (bash: `-o pipefail`; PowerShell: `$ErrorActionPreference = 'Stop'`; sh: none).
- **Companion `shell`:** `bash`, `sh`, `pwsh`, `powershell` (v0.1); `zsh`, `fish` (*later*). Without `shell`, the shell comes from `defaults.shell`, then the implementation's configuration, then detection (bash → sh on Unix, pwsh → powershell on Windows).
- A reached `script` whose shell isn't supported on the current OS fails the node; statically false `host:` branches are pruned first.
- The text is executed as written; it never interpolates `${…}`. Plan variables reach it only through `env:` and `export:`.
- Success: exit 0 or a code in `ok_exit`.

### 2.3 `do` (v0.1)

Runs its children in order.

- **Companion `fail_fast`** (boolean, default `true`). With `true`, the first failing child fails the `do` and the remaining children don't start. With `false`, the remaining children still run, and the `do` fails at the end; the first failure in plan order is the primary error and the others are attached as causes.
- A capture of a child is visible to later siblings and after the `do` ([variables.md](variables.md)).

### 2.4 `all` (v0.1)

Runs its children in parallel; succeeds when all succeed.

- **Companion `concurrency`** (integer ≥ 1). Default: all children at once. An implementation MAY cap the effective concurrency of a node (for blokky-cli: `max_concurrency`, default 16); a cap reduces parallelism but never changes start order or results. Children start in declaration order; with a limit, the next child starts when a slot frees.
- **Companion `fail_fast`** (boolean, default `true`). With `true`, the first failure cancels the running children, prevents unstarted ones from starting, and fails the `all` once the cancelled children are confirmed dead. With `false`, all children run to completion and the `all` fails if any failed; errors are attached as with `do`.
- Two children MUST NOT capture the same variable name.

### 2.5 `any` (v0.1)

Succeeds as soon as one child succeeds; fails only when all fail.

- **Companion `concurrency`** (integer ≥ 1, default **1**, capped as for `all`). With 1, `any` is an ordered fallback: try the first child, and only if it fails, the next. With N > 1, up to N alternatives run at once, started in declaration order.
- When a child succeeds, running children are cancelled and unstarted ones never start.
- Only the winning child's captures are bound; different children MAY capture the same name (never an input's name).
- **All children fail:** the node fails with `BK_ANY_ALL_FAILED`; every child's error is attached as a cause, in plan order ([ADR 0003](../adr/0003-execution-defaults.md)).
- `fail_fast` and `on_body_failure` are not valid on `any`.

### 2.6 `race` (*later*)

Starts all children at once, in declaration order; the **first child to complete**, successfully or not, decides the node's outcome, and the others are cancelled. `concurrency` and `fail_fast` are not valid on `race`.

### 2.7 `if` (v0.1)

```yaml
- if: { path: package-lock.json, exists: true }
  then:
    - exec: [npm, ci]
  else:
    - exec: [npm, install]
```

- `if:` takes a condition ([conditions.md](conditions.md)). **Companions:** `then` (required, list of nodes) and `else` (optional, list of nodes). An else-if is an `if` node inside `else`.
- The condition is evaluated once, in the node's own scope (after its `cwd`, `env` and other scoping modifiers). True runs `then`, false runs `else` (or nothing). A condition error fails the node.
- The node's status is that of the branch that ran; with no `else` and a false condition, the node succeeds. Implementations SHOULD suggest `when` for an `if` without `else`.

### 2.8 `sleep` (v0.1)

`sleep: 30s` waits for the duration (`0s` allowed). The wait ends immediately on cancellation. No process is started.

### 2.9 `log` (v0.1)

`log: "Watching run ${RUN_ID}"` records a message.

- **Companion `level`:** `debug`, `info` (default) or `warn`.
- The message is a display string (`${X}` interpolation, secrets masked). It is part of the run result ([results.md](results.md)); where an implementation also shows it (for example on stderr) is up to the implementation. No process is started. `log` replaces `echo` leaves.

### 2.10 `fail` (v0.1)

`fail: "No release tag on ${BRANCH}"` fails the node.

- **Companion `code`:** a user error code (default `BK_FAIL`).
- The message is a display string. `retry: true` doesn't retry a `fail`; only a `retry:` condition matching its code does (§5.5).

### 2.11 `assert` (v0.1)

```yaml
- assert: { var: RUN_ID, matches: '^\d+$' }
  message: "No CI run found for branch ${BRANCH}"
  code: CI_RUN_NOT_FOUND
```

- `assert:` takes a condition. If it is true, the node succeeds; if false, the node fails with `code` (default `BK_ASSERT`) and `message`.
- **Companions:** `message` (display string, optional; the default names the condition) and `code` (optional).
- **A condition error** fails the node with the built-in condition-error code, not with `code`; the assertion's `message` and `code` are attached as context ([ADR 0002](../adr/0002-language-core.md), Q-n).

## 3. Leaf options

Leaf options are node-level siblings of `exec` or `script`; on any other kind they are plan errors. A mapping given as the value of `exec:` or `script:` (`exec: { cmd: …, timeout: 5m }`) is a plan error whose fix-it moves the options to the node.

| Option | Milestone | Default | Meaning |
|---|---|---|---|
| `stdin` | v0.1 | empty | The leaf's standard input (below). |
| `ok_exit` | v0.1 | none | Extra exit codes that count as success. |
| `stderr` | v0.1 | separate | `merge` sends stderr into the stdout stream. |
| `encoding` | v0.1 | `utf-8` | How output is decoded for tails, captures and conditions. |
| `max_log_bytes` | v0.1 | implementation-defined | Cap on how much of this leaf's output the implementation keeps. |
| `keep_descendants` | v0.1 | `false` | Don't kill the leaf's remaining processes at leaf completion. |
| `capture` | v0.1 | — | Bind stdout (or JSON fields of it) to variables. |
| `capture_file` | v0.1 | — | Write stdout to a runtime-owned file and bind its path. |
| `secret` | v0.1 | `false` | Mark all captures of this node as secret. |

- **`stdin`.** By default a leaf's stdin is empty (`/dev/null`, or `NUL` on Windows); leaves never read the terminal. `stdin: "text"` passes literal text; `stdin: { var: X }` passes a variable's value; `stdin: { file: P }` passes the content of host file `P` (literal or `{ var: X }`, relative to the node's cwd).
- **`ok_exit`.** A list of integers; exit 0 always succeeds. On Windows, exit codes are unsigned 32-bit values.
- **`stderr: merge`.** Both streams go to one pipe, so their interleaving is kept; captures and `result: stdout` then include stderr text.
- **`encoding`.** `utf-8`, `utf-16le`, `utf-16be` or `latin1`. Invalid sequences become U+FFFD wherever output is shown as text; captures treat them as errors ([variables.md](variables.md)).
- **`max_log_bytes`.** A size; past it, the implementation stops keeping the leaf's output (with a truncation marker), and the leaf keeps running. It never limits what a capture or `result:` condition sees beyond their own limits.
- **`keep_descendants: true`.** By default, when the leaf's direct child exits, its remaining process group, session or job is killed. With `true` they keep running. Every descendant still dies no later than run end.
- **`capture`, `capture_file`, `secret`.** `capture: NAME` binds stdout with trailing CR/LF removed; `capture: { NUM: .number, STATE: .state }` binds JSON fields of stdout; `capture_file: NAME` binds the path of a file holding stdout. Over `max_capture_bytes` (1 MiB) or containing a NUL byte, a capture fails the node; it never truncates. Captures are bound only if the node succeeds. Binding and scope: [variables.md](variables.md).

## 4. Modifiers

| Modifier | Milestone | Valid on | Summary |
|---|---|---|---|
| `name` | v0.1 | all | Display label. |
| `when` | v0.1 | all | Run only if a condition holds, else `skipped`. |
| `timeout` | v0.1 | all | Total wall-clock limit. |
| `lock` | *later* | see §7 | Hold a named advisory lock. |
| `tempdir` | v0.1 | see §7 | Create a runtime-owned temp dir and make it the cwd. |
| `cwd` | v0.1 | see §7 | Working directory. |
| `env` | v0.1 | see §7 | Scoped environment variables. |
| `export` | v0.1 | see §7 | Export plan variables as environment variables. |
| `container` | *later* | see §7 | Run leaves in an ephemeral container. |
| `become` | *later* | see §7 | Run leaves as another user. |
| `services` | *later* | see §7 | Background processes around the node. |
| `finally` | v0.1 | all | Cleanup nodes, run once per node. |
| `ignore_errors` | v0.1 | all | The node's failure doesn't fail its parent. |
| `retry`, `while`, `until`, `for` | v0.1 (`for` sources partly *later*) | see §7 | Repetition (§5). |
| `attempt_timeout` | v0.1 | with repetition | Per-attempt or per-iteration limit. |

### 4.1 `name` (v0.1)

A display string, rendered per attempt or iteration (`name: build ${PROJ}`). The run result keeps the raw template for the node and the rendered text for each attempt and iteration. `name` never affects execution and need not be unique; nodes are identified by path ids. Implementations SHOULD warn about identical static names among siblings.

### 4.2 `when` (v0.1)

A guard condition, evaluated **once, before anything else, in the parent's scope**. If it is false, the node is `skipped`: it takes no lock, creates no tempdir, starts nothing and runs no `finally`. A condition error fails the node. A `when` that uses relative paths or probes on a node that sets `cwd`, `container` or `become` gets the `when-scope` lint warning, because those apply only inside the node.

### 4.3 `timeout` (v0.1)

The node's **total** wall-clock limit, measured on a monotonic clock. It covers lock wait, tempdir creation, container and service startup, the body and every repetition, but not `finally` (which has its own limit). When it fires, running processes get the graceful signal, then the forced kill after the grace period (5s), and the node fails with `BK_TIMEOUT_TOTAL`, status `timed_out`. The grace period comes after the limit ([ADR 0003](../adr/0003-execution-defaults.md), Q-k). Nested limits combine as the minimum.

There is no implicit `timeout` on groups or the root; `defaults.leaf_timeout` sets one for leaves and probes only. An implementation may also stop a whole run from outside ([execution-model.md §7](execution-model.md#7-external-stops)).

### 4.4 `lock` (*later*)

`lock: NAME` or `lock: { name: NAME, wait: 2m }` holds an OS advisory lock (`flock`, `LockFileEx`) named `NAME` for the node's duration. Waiting is bounded by `wait` (within the node's `timeout`); giving up fails the node with a distinct code. A node with `lock` MUST NOT have a descendant with `lock`, including in `finally` and `services` ([ADR 0005](../adr/0005-containers-become-locks.md)).

### 4.5 `tempdir` (v0.1)

`tempdir: true` or `tempdir: { as: WORK, prefix: build }`.

- Creates a fresh directory (mode 0700, unpredictable name, optional `prefix`) under the per-user temp root, **once per node** (not per attempt; nest `retry` inside to get a fresh dir per attempt).
- The directory **becomes the node's cwd**. A relative `cwd` on the same node resolves inside it; an absolute `cwd` together with `tempdir` is a plan error.
- `as` binds the directory's absolute path to a variable visible inside the node.
- The directory is not deleted when the node or the run ends; removing it is the implementation's business (for blokky-cli: `blokky clean`).
- `prefix` matches `^[A-Za-z0-9._-]{1,32}$`.

### 4.6 `cwd` (v0.1)

The working directory for the node and everything inside it: a literal path or `{ var: X }`. A relative path resolves against the parent's cwd (at the root: the invocation cwd), so paths are built by nesting. A cwd that doesn't exist or isn't a directory when the node starts fails the node.

### 4.7 `env` and `export` (v0.1)

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

### 4.8 `container` (*later*)

`container: { image, mounts, user, env_pass }` runs the node's leaves in an ephemeral container started for the node and stops (not removes) afterwards. By default the cwd is mounted read-write at the same path. Full semantics: [containers-and-privilege.md](containers-and-privilege.md).

### 4.9 `become` (*later*)

`become: USER`, `become: invoker` or `become: { user: USER }` runs the node's leaves and probes as another user, through `sudo -n` or `doas -n`, or by dropping privileges when the run has root privileges. Implementations MAY require an explicit opt-in to enable `become`. Full semantics: [containers-and-privilege.md](containers-and-privilege.md).

### 4.10 `services` (*later*)

`services: [ { name, exec | script, shell, env, export, cwd, ready, ready_timeout } ]` starts background processes before the node's body and stops them (whole process tree) after it. Each service's `ready:` condition is polled until it holds, within `ready_timeout`; it may use the service-only subjects `{ port: N, open: true }` (loopback) and `{ output: stdout, contains: … }`, plus `probe`. A service that exits before it is ready fails the node.

### 4.11 `finally` (v0.1)

A list of cleanup nodes that runs **once per node** (not per attempt or iteration) after the node's body ends, whether it succeeded, failed, timed out or was cancelled.

- **Companion `finally_timeout`** (duration, default 5m). `finally` runs under it even after the node's `timeout` fired; when the runtime stops the whole run, it may get less time ([execution-model.md §7](execution-model.md#7-external-stops)).
- A node skipped by `when` runs no `finally`.
- `finally` runs inside the node's tempdir, cwd, env, container and services, and sees what the body bound.
- **Errors:** a failing `finally` fails an otherwise successful node. If the body failed too, the body error is primary and the `finally` error is attached.
- Captures under `finally` are visible only to later nodes in the same `finally` list ([ADR 0002](../adr/0002-language-core.md), Q-s).

### 4.12 `ignore_errors` (v0.1)

`ignore_errors: true`: if the node fails, its parent treats it as not failed. The run result shows status `failed` with `ignored: true`. It never hides an outer cancellation, an ancestor's timeout or an external stop. A node whose failure is ignored binds no captures (use `ok_exit` when a capture should survive a known exit code).

### 4.13 `attempt_timeout` (v0.1)

A limit for each attempt (`retry`) or iteration (`while`, `until`, `for`), valid only together with a repetition modifier. It covers the body only: not the condition (probes have their own timeouts), not the `every` wait. When it fires, the attempt's processes are killed (graceful, then forced) and the attempt fails with `BK_TIMEOUT_ATTEMPT`.

## 5. Repetition

### 5.1 Common rules

- A node has **at most one** of `retry`, `while`, `until`, `for`. Combinations are written by nesting nodes.
- Repetition sits inside `finally` in the modifier order, so `finally`, `tempdir`, `cwd`, `env` and the scoping modifiers apply once around all attempts or iterations.
- The run result records the number of attempts or iterations, which bound ended the loop (`condition`, `max`, `timeout`), the last condition result, and per-iteration entries (rendered name, index, item).

### 5.2 Sibling fields

| Field | `retry` | `while` | `until` | Default |
|---|---|---|---|---|
| `max` (total attempts or iterations, integer ≥ 1) | yes | yes | yes | `retry`: 3; `while`/`until`: none (see §5.6) |
| `every` (duration, `0s` allowed) | yes | yes | yes | 1s |
| `attempt_timeout` | yes | yes | yes | none |
| `backoff: { factor, max }` | yes | — | — | none (fixed delay) |
| `jitter` | yes | — | — | none |
| `on_body_failure: stop \| continue` | — | yes | yes | `while`: `stop`; `until`: `continue` |

Using a field where the table says "—" is a plan error.

### 5.3 `every`, `backoff` and `jitter`

- **`every`** is the delay between the **end** of one attempt or iteration (including its condition check) and the **start** of the next. There is no delay before the first. The default is 1s, so a loop never runs back to back by accident; `every: 0s` removes the delay. Waits end immediately on cancellation.
- **`backoff: { factor: F, max: D }`** (`retry` only) grows the delay: the delay before attempt n+1 is `every × F^(n−1)`, capped at `max`. `factor` is a decimal from 1 to 10 and required in the mapping; `max` is a duration, default 5m.
- **`jitter: J`** (`retry` only, decimal 0 < J ≤ 1) multiplies each delay by a random value in [1 − J, 1], drawn from a seedable RNG so tests are reproducible.

### 5.4 `retry` (v0.1)

`retry: true` or `retry: <condition>`.

1. Run attempt 1.
2. If it succeeds, the node succeeds, and captures on the node are bound from it.
3. If it fails, decide whether to retry: with `retry: true`, by the table in §5.5; with a condition, by evaluating it against the failed attempt (the `result:` subject sees its `stdout`, `stderr`, `exit` and `error`; after an `attempt_timeout`, `error` is `BK_TIMEOUT_ATTEMPT`).
4. If no retry is warranted, the node fails with the attempt's error.
5. If attempts reached `max`, the node fails with `BK_RETRIES_EXHAUSTED`, with the last attempt's error nested.
6. Otherwise wait the delay (§5.3) and run the next attempt.

`on_body_failure` is not valid on `retry`.

### 5.5 What `retry: true` retries

| Failure of an attempt | Retried by `retry: true` | Retried by a `retry:` condition |
|---|---|---|
| Non-zero exit (not in `ok_exit`), killed by a signal | yes | if the condition holds |
| `BK_TIMEOUT_ATTEMPT` | yes | if the condition holds |
| Capture failure (missing JSON path, over the size limit, NUL byte) | yes | if the condition holds |
| `fail` or `assert` with a user code | no | if the condition matches the code |
| Condition error | no | if the condition matches the condition-error code |
| Spawn error (program not found, not executable) | no | if the condition matches the code |
| `BK_TIMEOUT_TOTAL`, cancellation, external stops | never | never |

For a group node with `retry`, "attempt failed" means the group failed, and the group's error code is what the table and condition see.

### 5.6 `while` and `until` (v0.1)

- **Bounded loops:** `while` and `until` MUST have `max`, `timeout`, or both. An unbounded loop is a plan error.
- **`while: <condition>`** checks the condition **before** each iteration. The first check sees only the enclosing scope; later checks also see the previous iteration's captures. False ends the loop successfully, so a `while` that is false at the first check succeeds with zero iterations (`ended_by: condition`).
- **`until: <condition>`** checks the condition **after** each successful iteration; true ends the loop successfully. Polling is `until` with a `result:` condition.
- **Body failure** (including `BK_TIMEOUT_ATTEMPT`): with `on_body_failure: stop`, the node fails with the body's error. With `continue`, the iteration counts as "not done yet": no condition is checked, and the loop goes on to the next iteration after the delay.
- **Reaching `max`** without the condition ending the loop fails the node with `BK_LOOP_MAX_REACHED`, with the last iteration's error (if any) nested. Reaching `timeout` fails with `BK_TIMEOUT_TOTAL`.
- Captures on the repeating node itself are bound from the terminating iteration; captures in a loop body are scoped to the loop ([variables.md](variables.md)).

### 5.7 `for` (v0.1; some sources *later*)

All `for` options live inside the `for:` mapping:

```yaml
- name: build ${PROJ}
  for: { glob: "src/**/*.csproj", as: PROJ, concurrency: 4 }
  exec: [dotnet, build, { var: PROJ }, -c, Release]
```

**Sources** (exactly one):

| Source | Milestone | Items |
|---|---|---|
| `each: [a, b, c]` | v0.1 | The listed strings (non-empty list). |
| `count: N` | v0.1 | `0` … `N−1`; `count: 0` runs zero iterations and succeeds. |
| `glob: "pattern"` | v0.1 | Matching host paths, expanded by Blokky (below). |
| `items: { var: X, json: .path }` | *later* | Elements of a JSON array in a captured variable. |
| `lines: { var: X }` | *later* | Lines of a captured variable. |
| `matrix: { OS: [..], ARCH: [..] }` | *later* | The Cartesian product; binds each key as a variable. |

**Options:**

- `as` (variable name): **required** for every source except `matrix`, where it is forbidden. It binds the item; `<AS>_INDEX` binds the **0-based** index. For `matrix`, the index is `MATRIX_INDEX` and the result's item is an object.
- `concurrency` (integer ≥ 1, default 1, capped by `max_concurrency`): above 1 the loop is a fan-out; iterations start in item order.
- `fail_fast` (boolean, default `true`): as for `all`.
- `allow_empty` (boolean, default `false`, `glob` only): zero matches succeed with zero iterations instead of failing.
- `max_items` (integer, default 1000, `items` and `lines` only, *later*): more items fail the node before the first iteration; items are never truncated.

**Glob rules:** ordinal sort of the matches; no dotfiles unless the pattern names them; no symlink following; `/` separators in item values; no `..` escaping the cwd subtree; zero matches is an error unless `allow_empty: true`. Patterns are host paths relative to the node's cwd.

**Iterations** never publish captures to the enclosing scope (*later*: only through `collect`). A for-loop's iteration count and items are in the run result. Item values and inputs used as `exec` arguments should be preceded by `--` where the program supports it.

**`collect`** (*later*): `collect: { CAPTURE: LISTVAR }` on a `for` node binds `LISTVAR` to the list of each iteration's `CAPTURE` value, in item order, with `null` for failed or skipped iterations.

## 6. Plan-level keys

`blokky`, `inputs`, `outputs` and `defaults` are allowed only at the root; see [syntax.md §4](syntax.md#4-the-plan-document) and [variables.md](variables.md). The root mapping is also the root node: it holds exactly one kind and may carry modifiers.

## 7. Validity matrix

Which modifiers and companion groups each kind accepts. ✓ = valid; — = plan error. `name`, `when`, `timeout`, `finally` (with `finally_timeout`) and `ignore_errors` are valid on every kind and not repeated below.

| Kind | Scope (`cwd`, `env`, `export`, `tempdir`, `lock`, `container`, `become`, `services`) | `retry`, `while`, `until` | `for` | `attempt_timeout` | Leaf options (§3) | `concurrency` | `fail_fast` |
|---|---|---|---|---|---|---|---|
| `exec` | ✓ | ✓ | ✓ | with repetition | ✓ | `for` only | `for` only |
| `script` | ✓ | ✓ | ✓ | with repetition | ✓ | `for` only | `for` only |
| `do` | ✓ | ✓ | ✓ | with repetition | — | `for` only | ✓ |
| `all` | ✓ | ✓ | ✓ | with repetition | — | ✓ | ✓ |
| `any` | ✓ | ✓ | ✓ | with repetition | — | ✓ | `for` only |
| `race` (*later*) | ✓ | ✓ | ✓ | with repetition | — | — | `for` only |
| `if` | ✓ | ✓ | ✓ | with repetition | — | `for` only | `for` only |
| `assert` | ✓ | ✓ | ✓ | with repetition | — | `for` only | `for` only |
| `log` | — | — | ✓ | — | — | `for` only | `for` only |
| `sleep` | — | — | — | — | — | — | — |
| `fail` | — | — | — | — | — | — | — |

"`for` only" means the field is valid only inside the `for:` mapping of that node. Companion fields of a kind (`then`/`else`, `shell`, `level`, `message`, `code`) are valid only on their kind.

## 8. Rules the schema doesn't express

Implementations MUST enforce these as plan errors (unless noted) in addition to the schema:

1. Exactly one kind per node.
2. At most one repetition modifier per node.
3. The validity matrix (§7) and the per-repetition sibling table (§5.2).
4. `attempt_timeout` only with a repetition modifier.
5. `while` and `until` have `max` or `timeout` (or both).
6. Modifiers outside repetition (`when`, `timeout`, `lock`, `tempdir`, `cwd`, `env`, `container`, `become`, `services`) don't reference variables the node itself introduces (`as`, `tempdir.as`, its own captures): "move it into the body".
7. Shadowing: no variable name is bound twice in nested scopes; inputs collide with every other binding.
8. Two `all` children don't capture the same name.
9. Inputs and variables never reach literal fields; argv[0] of an `exec` array is a literal.
10. `env` doesn't set a forbidden key; `export` doesn't name a reserved environment name; no name is in both `env` and `export` on one node.
11. An absolute `cwd` is not combined with `tempdir` on one node.
12. Captures (`capture`, `capture_file`, `secret`) only on `exec` and `script` nodes.
13. The `result:` subject only in `until` and `retry` conditions; `result: stdout|stderr|exit` only when the node's kind is `exec` or `script`.
14. `not:` isn't wrapped around a simple condition that has a `not_*` form.
15. An `outputs` entry isn't bound only inside a loop body (*later*: unless collected).
16. Captures under `finally` aren't referenced outside that `finally` list.
17. No `lock` inside a `lock` (*later*).
18. `as` is present for scalar `for` sources and absent for `matrix`.
19. A secret marker is only on references, never on literals.
20. An input's `default` satisfies its constraint; at most one of `in`/`matches`.
21. Empty lists only in fields that allow them (`mounts`).
22. A regex compiles under `RegexOptions.NonBacktracking`.
23. `${X}` names a variable in scope (a warning when it might be undefined; a run-time error when it is).

## 9. Security considerations

- **Baseline.** Running a plan is equivalent to running the same commands in bash: Blokky grants no capability, bypasses no permission system and hides nothing that will run. Everything a plan can execute is determinable from the plan and its inputs before it runs, so implementations can show it for review (for blokky-cli: [`leaves`](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/leaves-and-validation.md)).
- **Hygiene is not a control.** Lint, secret masking and display sanitization make plans cleaner and more reviewable; they don't decide what may run. Deciding is the job of controls outside the language: the agent runner's permission system and the implementation's approval mechanisms (for blokky-cli: the hook and validator).
- **Dynamic code.** A variable used as code (`sh -c` with a variable, `eval`, `iex`), execution-influencing environment variables, dynamic nested plans, dynamic stdin into an interpreter and a dynamic cwd are statically recognizable, so implementations can flag them for review.
- **Argument injection.** Item values, captures and inputs passed as `exec` arguments can start with `-`; put `--` before them where the program supports it.
- **Secrets.** Masking doesn't follow derived values, and conditions on secrets act as oracles. Secrets come only by reference, so their values never appear in the plan or in a static view of it.
- **Probes** should be side-effect-free; they run as real processes in the node's scope.
- **Containers** (*later*) are not a sandbox by default; mounting the engine socket or running privileged is equivalent to host root.
- **`become`** (*later*) uses passwordless `sudo -n`/`doas -n` only; Blokky never prompts for or forwards passwords.
- **Resource bounds** (timeouts, caps, the concurrency cap) exist for predictability, not as security boundaries.
