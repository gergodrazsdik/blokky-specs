# Conditions

Status: **draft** (spec 0.1, not yet finalized)

This document is normative for conditions: the one construct used by `if`, `when`, `assert`, `while`, `until`, `retry` and (*later*) `ready`. It defines the shape, subjects, operators, composites, probes, condition errors and the scope a condition is evaluated in. Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions). Rules carry IDs (`CO-n`) for conformance cases.

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

| Subject | Milestone | Value tested |
|---|---|---|
| `var: NAME` | v0.1 | Plan variable `NAME` ([variables.md](variables.md)). |
| `env: NAME` | v0.1 | Environment variable `NAME` in the **effective** environment of the scope where the condition is evaluated (Blokky's environment plus enclosing `env`/`export`). |
| `path: P` | v0.1 | Host filesystem path `P` (literal or `{ var: X }`), relative to the cwd of the evaluating scope. |
| `host: os \| arch` | v0.1 | `os` ∈ {`linux`, `macos`, `windows`} (WSL is `linux`); `arch` ∈ {`x64`, `arm64`}. |
| `result: stdout \| stderr \| exit \| error` | v0.1 | The node's own last attempt or iteration (§2.1). |
| `probe: { … }` | v0.1 | A probe's exit code, or its trimmed stdout when an operator is given (§5). |
| `port: N` | *later* | A loopback TCP port; `services` `ready:` conditions only. |
| `output: stdout \| stderr` | *later* | A service's output so far; `services` `ready:` conditions only. |

### 2.1 `result`

- **CO-5.** `result:` is valid only in `until` and `retry` conditions. `result: stdout`, `stderr` and `exit` are valid only when the node's kind is `exec` or `script`.
- **CO-6.** `stdout` and `stderr` are the attempt's full output (decoded and trimmed as for captures), up to `max_capture_bytes`; larger output makes the condition a condition error. `exit` is the exit code as a decimal string. `error` is the attempt's error code (`''` if it succeeded); after an `attempt_timeout` it is `BK_TIMEOUT_ATTEMPT`.

### 2.2 `host`

- **CO-7.** `host:` is the only subject evaluated statically: a branch whose `host:` condition is false on this machine is **pruned** before the shell and OS checks and in static views of the plan. A `host:` condition inside a composite with other subjects is evaluated at run time like any other.

## 3. Operators

| Operator | Negation | Operand | Valid subjects |
|---|---|---|---|
| `equals` | `not_equals` | string | `var`, `env`, `result`, `probe`, `host` |
| `in` | `not_in` | non-empty list of strings | `var`, `env`, `result`, `probe`, `host` |
| `contains` | `not_contains` | string (plain substring) | `var`, `env`, `result` (`stdout`, `stderr`), `probe`, `output` (*later*) |
| `matches` | `not_matches` | regex | `var`, `env`, `result` (`stdout`, `stderr`), `probe`, `output` (*later*) |
| `empty` | `not_empty` | `true` | `var`, `env`, `result` (`stdout`, `stderr`, `error`), `probe` |
| `defined` | `not_defined` | `true` | `var`, `env` |
| `exists` | `not_exists` | `true` | `path` |
| `is_file`, `is_dir` | — (use `not:`) | `true` | `path` |
| `open` | — | `true` | `port` (*later*) |
| `gt`, `ge`, `lt`, `le` | (complementary) | number | `var`, `env`, `result` (`stdout`, `exit`), `probe` |

- **CO-8.** Unary operators take the value `true` only.
- **CO-9.** Operand values are literals ([syntax.md §7.4](syntax.md#74-per-field-table)).
- **CO-10.** A single negation uses the `not_*` form. `not:` around a simple condition whose operator has a `not_*` form is a plan error with a fix-it.

### 3.1 String operators

- **CO-11.** `equals`, `in` and `contains` compare strings ordinally. Nothing is trimmed except process output, which has all trailing `\n` and `\r` removed when it becomes a value ([ADR 0002](../adr/0002-language-core.md)).
- **CO-12.** `ignore_case: true` makes `equals`, `in`, `contains` (ordinal, case-insensitive) and `matches` (as `(?i)`) ignore case, using the invariant culture. On other operators it is a plan error.

### 3.2 `matches`

- **CO-13.** `matches` is an **unanchored search over the whole value**: true if the pattern matches anywhere. It uses .NET regular expressions with `RegexOptions.NonBacktracking` and the invariant culture.
- **CO-14.** There is no implicit multiline mode: `^` and `$` anchor at the start and end of the whole value. Inline options (`(?m)`, `(?s)`, `(?i)`) are allowed. In .NET, `$` also matches before a final newline; use `\z` for a strict end.
- **CO-15.** A pattern that doesn't compile under `NonBacktracking` is a plan error.

### 3.3 Emptiness and definedness

- **CO-16.** `empty` is true for `''`. `defined` is true if the variable is bound (for `var`) or set (for `env`, even if empty).
- **CO-17.** `empty`/`not_empty` on an undefined variable is a condition error; write `{ any: [ { var: X, not_defined: true }, { var: X, empty: true } ] }` for "undefined or blank" ([ADR 0002](../adr/0002-language-core.md), Q-m).

### 3.4 Path operators

- **CO-18.** `exists`, `is_file` and `is_dir` follow symbolic links: a link to a file is a file; a dangling link doesn't exist. Permission errors while checking are condition errors.

### 3.5 Numeric operators

- **CO-19.** For `gt`, `ge`, `lt` and `le`, both the value and the operand MUST match `^-?[0-9]+(\.[0-9]+)?$` and are compared as exact decimals (leading zeros allowed). A leading `+`, exponents, hex, separators, whitespace, `.5`, `5.`, `NaN` and `Infinity` are condition errors in the value and plan errors in the operand ([ADR 0002](../adr/0002-language-core.md), Q3c).

### 3.6 `json:`

- **CO-20.** `json: PATH` parses the subject's value as one JSON value and extracts the value at `PATH` before the operator applies. Paths use the subset `.`, `.name`, `.["key"]`, `[N]` ([syntax.md](syntax.md), [ADR 0002](../adr/0002-language-core.md)).
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
- **CO-29.** Its limit is its own `timeout`, else the smaller of `probe_timeout` (default 30s) and `defaults.leaf_timeout` if set ([ADR 0003](../adr/0003-execution-defaults.md)).
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
| `while` | before each iteration | the node's own scope; the first check sees only the enclosing bindings |
| `until` | after each successful iteration | the node's own scope, plus the iteration's captures |
| `retry: <condition>` | after each failed attempt | the node's own scope, plus the attempt's captures and `result:` |
| `ready` (*later*) | polled until true | the service's scope |

- **CO-36.** "The node's own scope" means after the node's `tempdir`, `cwd`, `env`, `container` and `become` apply ([execution-model.md](execution-model.md), EM-8).
- **CO-37.** Implementations SHOULD warn about a `when` that uses a relative `path:` or a probe on a node that sets `cwd`, `container` or `become`, because those apply only inside the node.

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
  - a probe that can't be started (program not found);
  - a permission error while checking a `path`.
- **CO-39.** In `assert`, a condition error fails the node with the condition-error code, not the assertion's `code`; the assertion's `message` and `code` are attached as context ([ADR 0002](../adr/0002-language-core.md), Q-n).
- **CO-40.** In `retry`, `while` and `until`, a condition error ends the repetition and fails the node; `retry: true` doesn't retry it ([reference.md §5.5](reference.md#55-what-retry-true-retries)).
- **CO-41.** In `when`, a condition error fails the node; `ignore_errors` on that node applies ([ADR 0009](../adr/0009-status-propagation.md)).

## 8. Out of scope

Conditions don't do arithmetic, string manipulation, templating, semver comparison or HTTP checks, and there is no "end the plan successfully" construct. A check that needs more than a subject and an operator is a probe.
