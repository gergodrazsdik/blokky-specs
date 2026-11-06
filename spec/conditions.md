# Conditions

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is normative for conditions: the one construct used by `if`, `when`, `assert`, `while`, `until`, `retry` and `ready`. It defines the shape, subjects, operators, composites, probes, condition errors and the scope a condition is evaluated in. Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions). Rules carry IDs (`CO-n`) for conformance cases.

## 1. Shape

A condition is a mapping in one of four forms:

```yaml
{ var: STATUS, in: [queued, in_progress] }          # simple: one subject + one operator
{ probe: { exec: [docker, info] } }                 # bare probe: true by exit code
{ all: [ { var: A, equals: x }, { env: CI, defined: true } ] }   # composite
{ not: { path: build, is_dir: true } }              # negation
```

- **CO-1.** A **simple condition** has exactly one subject key and exactly one operator key, plus the optional modifiers `json:` and `ignore_case:`.
- **CO-2.** A **bare probe** is a `probe:` subject with no operator; it is true or false by the probe's exit code (§5). It is the only form without an operator.
- **CO-3.** A **composite** is `all: [ … ]`, `any: [ … ]` (non-empty lists of conditions) or `not: <condition>`.
- **CO-4.** Anything else is a plan error with a targeted fix-it: a string (`if: "$X == 1"` → `{ var: X, equals: '1' }`), two subjects, two operators, a node where a condition is expected, or a condition where a node list is expected.

## 2. Subjects

All subjects are evaluated by Blokky without starting a process, except `probe`.

| Subject | Value tested |
|---|---|
| `var: NAME` | Plan variable `NAME` ([variables.md](variables.md)). |
| `env: NAME` | Environment variable `NAME` in the **effective** environment of the scope where the condition is evaluated (Blokky's environment plus enclosing `env`/`export`). |
| `path: P` | Host filesystem path `P` (literal or `{ var: X }`), relative to the cwd of the evaluating scope. |
| `command: NAME` | Whether program `NAME` can be found the way an `exec` argv[0] would be (§2.4). |
| `host: os \| arch` | `os` ∈ {`linux`, `macos`, `windows`} (WSL is `linux`); `arch` ∈ {`x64`, `arm64`}, the OS's native architecture, also when Blokky runs under emulation (Rosetta, x64 on Windows on Arm). |
| `result: stdout \| stderr \| exit \| error` | The node's own last attempt or iteration (§2.1). |
| `probe: { … }` | A probe's exit code, or its trimmed stdout when an operator is given (§5). |
| `port: N` | A loopback TCP port; `services` `ready:` conditions only (§2.3). |
| `output: stdout \| stderr` | The service's output so far; `services` `ready:` conditions only (§2.3). |

### 2.1 `result`

- **CO-5.** `result:` is valid only in `until` and `retry` conditions. `result: stdout`, `stderr` and `exit` are valid only when the node's kind is `exec` or `script`.
- **CO-6.** `stdout` and `stderr` are the attempt's full output (decoded and trimmed as for captures), up to `max_capture_bytes`; larger output makes the condition a condition error. `exit` is the exit code as a decimal string. `error` is the attempt's error code (`''` if it succeeded); after an `attempt_timeout` it is `BK_TIMEOUT_ATTEMPT`.

### 2.2 `host`

- **CO-7.** `host:` is the only subject evaluated statically: a branch whose `host:` condition is false on this machine is **pruned** before the shell and OS checks. Static views still show a pruned branch, marked as pruned with its condition, so a review on one OS sees what the plan runs on another ([ADR 0018](../adr/0018-review-semantics.md)). A `host:` condition inside a composite with other subjects is evaluated at run time like any other.

### 2.3 `port` and `output` (services)

- **CO-42.** `{ port: N, open: true }` is true when a TCP connection to port N succeeds on `127.0.0.1` or `::1`; the connection is closed at once. Nothing else is sent. Ports on other hosts can't be checked. A port a container engine publishes is often open before the service inside is ready (the engine's proxy accepts the connection), so for a containerized service a probe such as `pg_isready` is the better readiness check.
- **CO-43.** `output: stdout` or `stderr` is everything the service has written to that stream so far (decoded as UTF-8, trailing CR/LF removed, at most `max_capture_bytes`, the latest output kept). It is tested with `contains` or `matches`.
- **CO-44.** Both subjects are valid only in a service's `ready:` condition, where they refer to that service ([reference.md §4.9](reference.md#49-services)).

### 2.4 `command`

- **CO-45.** `{ command: NAME, exists: true }` is true if `NAME` resolves to a program by the rules for `exec` argv[0] ([shells.md §4](shells.md#4-executable-resolution)): on `PATH` from the environment the run started with (never the cwd), with the Windows `.com`/`.exe` rule, and as a path relative to the evaluating scope's cwd when `NAME` contains a separator. Nothing is started. `not_exists` is its negation.
- **CO-46.** `NAME` is a literal. Like `path:`, `command:` looks at the host, also under `container` (implementations SHOULD warn there). It is the portable way to choose between tools:

```yaml
- any:
    - when: { command: ruff, exists: true }
      exec: [ruff, check, .]
    - exec: [python3, -m, flake8, .]
```

## 3. Operators

| Operator | Negation | Operand | Valid subjects |
|---|---|---|---|
| `equals` | `not_equals` | string | `var`, `env`, `result`, `probe`, `host` |
| `in` | `not_in` | non-empty list of strings | `var`, `env`, `result`, `probe`, `host` |
| `contains` | `not_contains` | string (plain substring) | `var`, `env`, `result` (`stdout`, `stderr`), `probe`, `output` |
| `matches` | `not_matches` | regex | `var`, `env`, `result` (`stdout`, `stderr`), `probe`, `output` |
| `empty` | `not_empty` | `true` | `var`, `env`, `result` (`stdout`, `stderr`, `error`), `probe` |
| `defined` | `not_defined` | `true` | `var`, `env` |
| `exists` | `not_exists` | `true` | `path`, `command` |
| `is_file`, `is_dir` | — (use `not:`) | `true` | `path` |
| `open` | — | `true` | `port` |
| `gt`, `ge`, `lt`, `le` | (complementary) | number | `var`, `env`, `result` (`stdout`, `exit`), `probe` |

- **CO-8.** Unary operators take the value `true` only.
- **CO-9.** Operand values are literals ([syntax.md §7.4](syntax.md#74-per-field-table)).
- **CO-10.** A single negation uses the `not_*` form. `not:` around a simple condition whose operator has a `not_*` form is a plan error with a fix-it.

### 3.1 String operators

- **CO-11.** `equals`, `in` and `contains` compare strings ordinally. Nothing is trimmed except process output, which has all trailing `\n` and `\r` removed when it becomes a value ([ADR 0002](../adr/0002-language-core.md)).
- **CO-12.** `ignore_case: true` makes `equals`, `in`, `contains` (ordinal, case-insensitive) and `matches` (as `(?i)`) ignore case: two characters are equal if their Unicode simple uppercase mappings are equal (so `k` matches `K` but not the Kelvin sign `K`). On other operators it is a plan error.

### 3.2 `matches`

- **CO-13.** `matches` is an **unanchored search over the whole value**: true if the pattern matches anywhere. Patterns use the portable regex subset of [syntax.md §6.7](syntax.md#67-regular-expressions); implementations translate it for their engine ([ADR 0018](../adr/0018-review-semantics.md)).
- **CO-14.** There is no multiline mode: `^` and `$` anchor at the start and end of the whole value, and `$` never matches before a final newline. `(?i)` is the only inline option.
- **CO-15.** A pattern outside the subset is a plan error.

### 3.3 Emptiness and definedness

- **CO-16.** `empty` is true for `''`. `defined` is true if the variable is bound (for `var`) or set (for `env`, even if empty).
- **CO-17.** `empty`/`not_empty` on an undefined variable is a condition error; write `{ any: [ { var: X, not_defined: true }, { var: X, empty: true } ] }` for "undefined or blank" ([ADR 0002](../adr/0002-language-core.md), Q-m).

### 3.4 Path operators

- **CO-18.** `exists`, `is_file` and `is_dir` follow symbolic links: a link to a file is a file; a dangling link doesn't exist. Permission errors while checking are condition errors.

### 3.5 Numeric operators

- **CO-19.** For `gt`, `ge`, `lt` and `le`, both the value and the operand MUST match `^-?[0-9]+(\.[0-9]+)?$` and are compared as exact decimals (leading zeros allowed). A leading `+`, exponents, hex, separators, whitespace, `.5`, `5.`, `NaN` and `Infinity` are condition errors in the value and plan errors in the operand ([ADR 0002](../adr/0002-language-core.md), Q3c).

### 3.6 `json:`

- **CO-20.** `json: PATH` parses the subject's value as one JSON value and extracts the value at `PATH` before the operator applies. Paths use the grammar of [syntax.md §6.8](syntax.md#68-json-paths).
- **CO-21.** The extracted value is converted to a string as in field captures: strings unescaped, numbers as written, `true`/`false`, `null` as `''`, objects and arrays as compact JSON ([variables.md](variables.md), VA-23).
- **CO-22.** Invalid JSON or a path that doesn't resolve is a condition error, except with `defined`/`not_defined`, where a missing path counts as undefined.

## 4. Composites

- **CO-23.** `all` and `any` evaluate their conditions **in order and short-circuit**: `all` stops at the first false, `any` at the first true. Conditions after that point aren't evaluated, so their probes never start and their errors never occur.
- **CO-24.** A condition error in an evaluated operand makes the whole composite a condition error.
- **CO-25.** Condition `all`/`any` mirror node `all`/`any` in truth value but not in execution: they are sequential, never parallel.

## 5. Probes

```yaml
{ probe: { exec: [docker, info] } }                                   # true if exit 0
{ probe: { exec: queue-cli depth }, gt: 0 }                           # operator on trimmed stdout
{ probe: { exec: git diff --quiet HEAD~1 -- package-lock.json, true_exit: [1], false_exit: [0] } }
{ probe: { script: "(Get-Service sshd).Status", shell: pwsh }, equals: Running }
```

### 5.1 Shape

- **CO-26.** A probe mapping has exactly one of `exec:` (the same values as the `exec` kind) or `script:` (with optional `shell:`), plus optionally `env`, `export`, `timeout`, `true_exit`, `false_exit` and `timeout_result`. The key list is closed.
- **CO-27.** Probes inherit the evaluating scope's cwd, `env` and `export`; their own `env` and `export` add to it.

### 5.2 Process

- **CO-28.** A probe is a real process with full process control: its own session or job, empty stdin, tree kill. It is killed when its own timeout expires, when an enclosing limit fires or when the evaluating node is cancelled.
- **CO-29.** Its limit is its own `timeout`, else the smaller of `probe_timeout` (default 30s) and `defaults.leaf_timeout` if set ([ADR 0003](../adr/0003-execution-defaults.md)). Hitting it is a condition error (CO-35).
- **CO-30.** Its stdout is limited to 64 KiB (implementations MAY let users raise it); more is a condition error. Its stderr is treated like the node's other output.
- **CO-31.** Every executed probe is recorded in the run result (command, exit code, duration, result), and every probe is part of what a plan can execute ([reference.md §9](reference.md#9-security-considerations)).
- **CO-32.** Probes SHOULD be side-effect-free. Startup cost matters for tight polling: `exec` probes and Blokky-evaluated subjects (`path`, `var`) are fast; a `pwsh` probe can take a second to start.

### 5.3 Truth value

- **CO-33.** **Bare probe:** with neither list, exit 0 is true and any other exit code false. With only `true_exit`, listed codes are true and all others false; with only `false_exit`, listed codes are false and all others true. With both lists, a code in neither is a condition error.
- **CO-34.** **Probe with an operator:** the probe MUST first exit with a "true" code by the rules of CO-33 (0 by default); otherwise the condition is a condition error. The operator then applies to the probe's stdout, decoded as UTF-8 and with trailing `\n`/`\r` removed.
- **CO-35.** **Timeout:** a probe that times out is a condition error, unless `timeout_result: true` or `false` gives the value to use instead.

## 6. Where conditions are evaluated

| Construct | Evaluated | Scope |
|---|---|---|
| `when` | once, before the node | the **parent's** scope |
| `if` | once | the node's own scope |
| `assert` | once | the node's own scope |
| `while` | before each iteration | the node's own scope, plus `index` and `carry` variables; the first check sees only the enclosing bindings and those |
| `until` | after each successful iteration | the node's own scope, plus the iteration's captures and its `index` and `carry` variables |
| `retry: <condition>` | after each failed attempt | the node's own scope, plus the attempt's captures, its `index` and `result:` |
| `ready` | polled until true | the service's scope |

- **CO-36.** "The node's own scope" means after the node's `tempdir`, `cwd`, `env` and `container` apply ([execution-model.md](execution-model.md), EM-8).
- **CO-37.** Implementations SHOULD warn about a `when` that uses a relative `path:` or a probe on a node that sets `cwd` or `container`, because those apply only inside the node.

## 7. Condition errors

A condition error makes a condition **neither true nor false**. The node that owns the condition fails with the built-in condition-error code (named in [errors.md](errors.md)); a condition error never counts as false.

- **CO-38.** These are condition errors:
  - a reference to an undefined variable or unset environment variable, except with `defined`/`not_defined`;
  - `empty`/`not_empty` on an undefined variable;
  - a value that isn't a number for a numeric operator;
  - invalid JSON or an unresolvable path with `json:` (except `defined`/`not_defined`);
  - a probe exit code outside both `true_exit` and `false_exit`, or not "true" when an operator is given;
  - a probe timeout without `timeout_result`;
  - probe output over the limit, or `result:` output over `max_capture_bytes`;
  - a probe that can't be started (program not found; test for an installed program with the `command` subject instead, §2.4);
  - a permission error while checking a `path`.
- **CO-39.** In `assert`, a condition error fails the node with the condition-error code, not the assertion's `code`; the assertion's `message` and `code` are attached as context ([ADR 0002](../adr/0002-language-core.md), Q-n).
- **CO-40.** In `retry` and `while`, a condition error ends the repetition and fails the node; `retry: true` doesn't retry it. In `until`, a condition error from the `result:` subject (invalid JSON, a path that doesn't resolve, output over the limit) counts as a failed iteration and follows `on_body_failure`: with `continue` (the default) the loop goes on, with `stop` the node fails; other condition errors in `until` end the loop ([ADR 0018](../adr/0018-review-semantics.md)). See also [reference.md §5.5](reference.md#55-what-retry-true-retries).
- **CO-41.** In `when`, a condition error fails the node; `ignore_errors` on that node applies ([ADR 0009](../adr/0009-status-propagation.md)).

## 8. Out of scope

Conditions don't do arithmetic, string manipulation, templating, semver comparison or HTTP checks, and they don't end anything early: ending a sequence successfully is the `return` node's job ([reference.md §2.13](reference.md#213-return)). A check that needs more than a subject and an operator is a probe.
