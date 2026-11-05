# Errors

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is the catalogue of the built-in error codes of the language: plan errors, input errors and the node errors a plan can observe. It is normative for the code names, their meaning and how `retry: true` treats them. How errors are reported is up to the implementation ([results.md](results.md) gives the abstract model). Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions).

## 1. Codes

- **ER-1.** Built-in codes start with the reserved prefix `BK_` and match `^BK_[A-Z][A-Z0-9_]*$`. User codes (from `fail` and `assert`) match `^[A-Z][A-Z0-9_]*$` and MUST NOT start with `BK_`.
- **ER-2.** Codes are a contract. Within a major spec version a code is never renamed, removed or given a different meaning; new codes MAY be added in any release. Consumers MUST treat an unknown code as a generic failure of its kind.
- **ER-3.** Every error carries a code, a human-readable message (masked, display-sanitized) and, where useful, a `detail` object with machine-readable fields listed below, nested `causes` and `context`. Messages are not a contract; codes and `detail` fields are.

## 2. Kinds of errors

| Kind | When | Where it is defined |
|---|---|---|
| **Plan error** | Before anything runs: the plan text, its structure or a static rule is invalid. | §4; the rules in [syntax.md](syntax.md) and [reference.md §8](reference.md#8-rules-the-schema-doesnt-express) |
| **Input error** | Before anything runs: an input value is missing or invalid. | §3; [variables.md §4](variables.md#4-plan-inputs) |
| **Node error** | While the plan runs: a node fails. Plans observe node errors through `result: error`, `retry:` conditions and statuses. | §5 |

How an implementation reports errors (JSON formats, exit codes) and the errors it adds for its own concerns (command-line usage, configuration, approval, run budget, cleanup) are not part of the language; for the reference implementation they are in [blokky-cli `docs/contracts/errors.md`](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/errors.md).

## 3. Input errors

| Code | Meaning |
|---|---|
| `BK_INPUT_SYNTAX` | A malformed `--input` (no `=`, a bad name) or MCP `inputs` object (non-string value, duplicate key). |
| `BK_INPUT_UNKNOWN` | An input the plan doesn't declare. `detail.suggestion` gives a close name. |
| `BK_INPUT_DUPLICATE` | The same input given twice. |
| `BK_INPUT_MISSING` | A required input without a value. `detail.command` is the exact command to run. |
| `BK_INPUT_EMPTY` | An empty value for a required input. |
| `BK_INPUT_INVALID` | A value that violates `in`/`matches` (`detail.constraint`) or the character rules. |
| `BK_INPUT_TOO_LARGE` | A value over 4 KiB or all values over 32 KiB. |

## 4. Plan errors

Plan errors carry a line and column. `BK_PLAN_INVALID` covers every rule of [reference.md §8](reference.md#8-rules-the-schema-doesnt-express) and the static rules of the other spec files; `detail.rule` names the rule (for example `one-kind`, `bounded-loop`, `shadowing`), so new rules don't need new codes.

| Code | Meaning |
|---|---|
| `BK_PLAN_ENCODING` | Not UTF-8: a UTF-16/32 BOM or invalid UTF-8 ([syntax.md §2.2](syntax.md#22-encoding)). |
| `BK_PLAN_CHARACTER` | A character rejected by the character lint. `detail.codepoint`. |
| `BK_PLAN_TOO_LARGE` | Over 4 MiB, or nested deeper than 128 levels. |
| `BK_PLAN_YAML` | Not valid YAML, or a rejected YAML feature (anchor, alias, merge key, tag, directive, second document, complex key). |
| `BK_PLAN_DUPLICATE_KEY` | A key repeated in a mapping. |
| `BK_PLAN_UNKNOWN_KEY` | A key that isn't valid at its position. `detail.suggestion` from did-you-mean or the synonym table. |
| `BK_PLAN_NOT_SUPPORTED` | A feature the implementation doesn't support yet. `detail.feature`. |
| `BK_PLAN_VERSION` | `blokky:` missing, malformed or naming an unsupported version. `detail.supported` lists the supported versions. |
| `BK_PLAN_VALUE` | A value that doesn't match its field's type or grammar (a boolean that isn't `true`/`false`, a bad duration, a bare number, an empty value or list, a regex that doesn't compile). |
| `BK_PLAN_INVALID` | A structural or static semantic rule is violated. `detail.rule`. |

## 5. Node errors

"Retried" says whether `retry: true` retries the error ([reference.md §5.5](reference.md#55-what-retry-true-retries)); a `retry:` condition that matches the code can retry any node error except those marked "never".

### 5.1 Processes

| Code | Meaning | Retried |
|---|---|---|
| `BK_EXIT` | The leaf exited with a code that isn't 0 or in `ok_exit`. `detail.exit_code`. | yes |
| `BK_SIGNAL` | The leaf was killed by a signal it didn't get from Blokky (Unix). `detail.signal`. | yes |
| `BK_SPAWN_NOT_FOUND` | The program or shell couldn't be resolved. `detail.program`. | no |
| `BK_SPAWN_FAILED` | The OS refused to start the process (not executable, permission denied, a `.bat`/`.cmd` target). `detail.reason`. | no |
| `BK_ENV_TOO_LARGE` | The leaf's environment or one value exceeds the OS limit. `detail.name`. | no |
| `BK_SHELL_UNAVAILABLE` | The `script` shell isn't supported on this OS or isn't configured (Git Bash on Windows). | no |
| `BK_CWD_INVALID` | The node's cwd doesn't exist, isn't a directory or can't be entered. | no |
| `BK_TEMPDIR_FAILED` | The node's `tempdir` couldn't be created. | no |

### 5.2 Limits and cancellation

| Code | Meaning | Retried |
|---|---|---|
| `BK_TIMEOUT_TOTAL` | The node's own `timeout` (or `defaults.leaf_timeout`) fired. | never |
| `BK_TIMEOUT_ATTEMPT` | The node's `attempt_timeout` fired for one attempt or iteration. | yes |
| `BK_CANCELLED` | The node was cancelled from outside: a failing sibling, a decided `any`/`race`, an ancestor's limit, or the runtime stopping the run (run budget, shutdown; `detail.reason`). Its status is `cancelled`. | never |

### 5.3 Conditions, variables and captures

| Code | Meaning | Retried |
|---|---|---|
| `BK_CONDITION_ERROR` | A condition was neither true nor false ([conditions.md §7](conditions.md#7-condition-errors)). `detail.reason`: `undefined_variable`, `not_a_number`, `json_invalid`, `json_path`, `probe_exit`, `probe_timeout`, `probe_output_too_large`, `probe_spawn`, `output_too_large`, `path_access`. In `assert`, `context` holds the assertion's `message` and `code`. | no |
| `BK_UNDEFINED_VARIABLE` | A display string or reference used a variable that isn't bound at that point. `detail.name`. | no |
| `BK_FROM_ENV_UNSET` | A `{ from_env: NAME }` names an unset environment variable. `detail.name`. | no |
| `BK_CAPTURE_TOO_LARGE` | stdout exceeded `max_capture_bytes`. | yes |
| `BK_CAPTURE_NUL` | stdout contained a NUL byte. | yes |
| `BK_CAPTURE_ENCODING` | stdout isn't valid in the leaf's `encoding`. | yes |
| `BK_CAPTURE_JSON` | A field capture's stdout isn't one valid JSON value. | yes |
| `BK_CAPTURE_PATH` | A field capture's JSON path doesn't resolve. `detail.path`. | yes |

### 5.4 Explicit failures and aggregates

| Code | Meaning | Retried |
|---|---|---|
| `BK_FAIL` | A `fail` node without its own `code`. | no |
| `BK_ASSERT` | An `assert` whose condition was false, without its own `code`. | no |
| `BK_RETRIES_EXHAUSTED` | `retry` reached `max`; the last attempt's error is the cause. | — |
| `BK_LOOP_MAX_REACHED` | `while`/`until` reached `max` without the condition ending the loop; the last iteration's error, if any, is the cause. | — |
| `BK_ANY_ALL_FAILED` | Every child of an `any` failed; each child's error is a cause, in plan order. | as its causes |
| `BK_FINALLY_FAILED` | The node's body succeeded but its `finally` failed; the `finally` error is the cause. (If the body failed, its error stays primary and the `finally` error is attached.) | no |
| `BK_GLOB_EMPTY` | A `for: { glob }` matched nothing and `allow_empty` isn't set. | no |
| `BK_ITEMS_TOO_MANY` | `items`/`lines` produced more than `max_items`. | no |
| `BK_ITEMS_INVALID` | A `for: { items }` value isn't JSON, or its path doesn't select an array. | yes |

User codes from `fail` and `assert` (`code:`) are node errors too; `retry: true` doesn't retry them.

### 5.5 Later features

| Code | Meaning |
|---|---|
| `BK_LOCK_TIMEOUT` | A `lock` wasn't acquired within `wait`. |
| `BK_CONTAINER_FAILED` | The container couldn't be started or the engine failed. `detail.engine`. |
| `BK_CWD_UNMAPPED` | The node's cwd maps through no container mount. |
| `BK_SERVICE_NOT_READY` | A service's `ready:` condition didn't hold within `ready_timeout`. `detail.service`. |
| `BK_SERVICE_EXITED` | A service exited before it was ready, or (with `on_exit: fail`) after it was ready while the body ran. `detail.service`, `detail.exit_code`. |
| `BK_BECOME_DISABLED` | The plan uses `become`, but the implementation requires an opt-in that the user hasn't given (CP-22). |
| `BK_BECOME_FAILED` | The user switch failed: the elevation tool needed a password, the user doesn't exist, or the platform doesn't support it. |
