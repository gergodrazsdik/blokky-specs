# Errors

Status: **draft** (spec 0.1, not yet finalized)

This document is the catalogue of built-in error codes. It is normative for the code names, their meaning, the phase they occur in and how `retry: true` treats them. The JSON shape of an error object is in [output-contract.md](output-contract.md); exit codes are in blokky-cli `cli.md` ([blokky-cli ADR 0002](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/adr/0002-cli-run-lifecycle.md)). Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions).

## 1. Codes

- **ER-1.** Built-in codes start with the reserved prefix `BK_` and match `^BK_[A-Z][A-Z0-9_]*$`. User codes (from `fail` and `assert`) match `^[A-Z][A-Z0-9_]*$` and MUST NOT start with `BK_`.
- **ER-2.** Codes are a contract. Within a major spec version a code is never renamed, removed or given a different meaning; new codes MAY be added in any release. Consumers MUST treat an unknown code as a generic failure of its phase.
- **ER-3.** Every error carries a code, a human-readable message (masked, display-sanitized) and, where useful, a `detail` object with machine-readable fields listed below, nested `causes` and `context`. Messages are not a contract; codes and `detail` fields are.

## 2. Phases

| Phase | Where it is reported | Exit code |
|---|---|---|
| **Usage** | pre-run envelope | 2 |
| **Plan** | pre-run envelope; `plan`, `leaves`, `lint`, `validate` | 3 |
| **Config** | pre-run envelope | 4 |
| **Approval** | pre-run envelope; hook verdicts | 5, 6 or 7 (§4) |
| **Node** | the failing node's entry in the report | 1 (if it fails the run) |
| **Run** | the report's run-level `error` | 8, 128+N, 70 |
| **Cleanup** | `clean`/`gc` output; the report's `artifacts` | 9 |

## 3. Usage and input errors

| Code | Meaning |
|---|---|
| `BK_USAGE` | Malformed command-line flags or arguments (unknown flag, missing value, a disallowed spelling such as `--opt=v`). |
| `BK_INPUT_SYNTAX` | A malformed `--input` (no `=`, a bad name) or MCP `inputs` object (non-string value, duplicate key). |
| `BK_INPUT_UNKNOWN` | An input the plan doesn't declare. `detail.suggestion` gives a close name. |
| `BK_INPUT_DUPLICATE` | The same input given twice. |
| `BK_INPUT_MISSING` | A required input without a value. `detail.command` is the exact command to run. |
| `BK_INPUT_EMPTY` | An empty value for a required input. |
| `BK_INPUT_INVALID` | A value that violates `in`/`matches` (`detail.constraint`) or the character rules. |
| `BK_INPUT_TOO_LARGE` | A value over 4 KiB or all values over 32 KiB. |

## 4. Plan, config and approval errors

Plan errors carry a line and column. `BK_PLAN_INVALID` covers every rule of [reference.md §8](reference.md#8-rules-the-schema-doesnt-express) and the static rules of the other spec files; `detail.rule` names the rule (for example `one-kind`, `bounded-loop`, `shadowing`), so new rules don't need new codes.

| Code | Meaning |
|---|---|
| `BK_PLAN_ENCODING` | Not UTF-8: a UTF-16/32 BOM or invalid UTF-8 ([syntax.md §2.2](syntax.md#22-encoding)). |
| `BK_PLAN_CHARACTER` | A character rejected by the character lint. `detail.codepoint`. |
| `BK_PLAN_TOO_LARGE` | Over 4 MiB, or nested deeper than 128 levels. |
| `BK_PLAN_YAML` | Not valid YAML, or a rejected YAML feature (anchor, alias, merge key, tag, directive, second document, complex key). |
| `BK_PLAN_DUPLICATE_KEY` | A key repeated in a mapping. |
| `BK_PLAN_UNKNOWN_KEY` | A key that isn't valid at its position. `detail.suggestion` from did-you-mean or the synonym table. |
| `BK_PLAN_NOT_SUPPORTED` | A keyword of a later feature, or the reserved `consent`, in a spec version that doesn't support it. |
| `BK_PLAN_VERSION` | `blokky:` missing, malformed or naming an unsupported version. `detail.supported` lists the supported versions. |
| `BK_PLAN_VALUE` | A value that doesn't match its field's type or grammar (a boolean that isn't `true`/`false`, a bad duration, a bare number, an empty value or list, a regex that doesn't compile). |
| `BK_PLAN_INVALID` | A structural or static semantic rule is violated. `detail.rule`. |
| `BK_LINT` | A lint finding at severity `error`. `detail.rule` is the lint rule id. |
| `BK_CONFIG` | A config file can't be read or parsed, fails its schema, or a non-user file sets a user-only key. `detail.file`, `detail.key`. |
| `BK_SHA_MISMATCH` | The plan bytes don't match `--expect-sha256` (exit 7). |
| `BK_APPROVAL_REQUIRED` | `require_hook_approval` is on and `blokky run` got no `--approval` (exit 5). |
| `BK_APPROVAL_NOT_FOUND` | `--approval` names a record that doesn't exist or was already used (exit 5). |
| `BK_APPROVAL_EXPIRED` | The approval record is older than `approval_ttl` (exit 5). |
| `BK_APPROVAL_MISMATCH` | The run's cwd or resolved config/state locations differ from the approval record (exit 5). |
| `BK_DENIED` | The validator or runner-rules mode denied the invocation (`validate`, exit 6). |
| `BK_VALIDATOR_FAILED` | The validator timed out, crashed, was missing or answered invalid JSON; the verdict becomes `ask` (exit 5 for `validate`). |

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
| `BK_CANCELLED` | The node was cancelled from outside (a failing sibling, a decided `any`/`race`, an ancestor's limit). Its status is `cancelled`. | never |

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
| `BK_ITEMS_TOO_MANY` (*later*) | `items`/`lines` produced more than `max_items`. | no |

User codes from `fail` and `assert` (`code:`) are node errors too; `retry: true` doesn't retry them.

### 5.5 Later features

| Code | Meaning |
|---|---|
| `BK_LOCK_TIMEOUT` | A `lock` wasn't acquired within `wait`. |
| `BK_CONTAINER_FAILED` | The container couldn't be started or the engine failed. `detail.engine`. |
| `BK_CWD_UNMAPPED` | The node's cwd maps through no container mount. |
| `BK_SERVICE_NOT_READY` | A service's `ready:` condition didn't hold within `ready_timeout`. |
| `BK_SERVICE_EXITED` | A service exited before it was ready. |
| `BK_BECOME_DISABLED` | The plan uses `become`, but the user-only switch that enables it is off. |
| `BK_BECOME_FAILED` | The user switch failed: the elevation tool needed a password, the user doesn't exist, or the platform doesn't support it. |

## 6. Run errors

| Code | Meaning | Exit code |
|---|---|---|
| `BK_BUDGET_EXCEEDED` | The run budget was reached; Blokky cancelled the run. Leaves killed by it carry `killed_by: budget`. | 8 |
| `BK_INTERRUPTED` | Blokky received a signal or console control event and shut down. `detail.signal`. | 128+N |
| `BK_INTERNAL` | A bug in Blokky. The message asks for a report. | 70 |

## 7. Cleanup errors

| Code | Meaning | Exit code |
|---|---|---|
| `BK_CLEANUP_INCOMPLETE` | `clean`, `gc` or `run --cleanup` couldn't remove every artefact; the output lists each failure with its path and reason. | 9 (for `clean`/`gc`) |
| `BK_RUN_NOT_FOUND` | `clean` or `report` names a run id that isn't registered. | 2 |
| `BK_RUN_IN_PROGRESS` | `clean` names a run that is still in progress; nothing is deleted. | 2 |
