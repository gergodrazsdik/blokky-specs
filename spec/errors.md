# Errors

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is the catalogue of the built-in error codes of the language: plan errors, input errors and the node errors a plan can observe. It is normative for the code names, their meaning and how `retry: true` treats them. How errors are reported is up to the implementation ([results.md](results.md) gives the abstract model). Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions).

## 1. Codes

- **ER-1.** Built-in codes start with the reserved prefix `BK_` and match `^BK_[A-Z][A-Z0-9_]*$`. User codes (from `fail` and `assert`) match `^[A-Z][A-Z0-9_]*$` and MUST NOT start with `BK_`; a plan that breaks this is reported as SY-52 ([syntax.md](syntax.md) SY-3).
- **ER-2.** Codes are a contract. Within a major spec version a code is never renamed, removed or given a different meaning; new codes MAY be added in any release. Consumers MUST treat an unknown code as a generic failure of its kind.
- **ER-3.** Every error carries a code, a human-readable message (masked, display-sanitized) and, where useful, a `detail` object with machine-readable fields listed below, nested `causes` and `context`. Messages are not a contract; codes and `detail` fields are.

## 2. Kinds of errors

| Kind | When | Where it is defined |
|---|---|---|
| **Plan error** | Before anything runs: the plan text, its structure or a static rule is invalid. | §4; the rules in [syntax.md](syntax.md) and [reference.md §8](reference.md#8-rules-beyond-the-schema) |
| **Input error** | Before anything runs: an input value is missing or invalid. | §3; [variables.md §4](variables.md#4-plan-inputs) |
| **Node error** | While the plan runs: a node fails. Plans observe node errors through `result: error`, `retry:` conditions and statuses. | §5 |

How an implementation reports errors (JSON formats, exit codes) and the errors it adds for its own concerns (command-line usage, configuration, approval, run budget, cleanup) are not part of the language; for the reference implementation they are in [blokky-cli `docs/contracts/errors.md`](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/errors.md).

## 3. Input errors

| Code | Meaning |
|---|---|
| `BK_INPUT_SYNTAX` | A malformed `--input` (no `=`, a name that breaks the name grammar) or MCP `inputs` object (non-string value, duplicate key). |
| `BK_INPUT_UNKNOWN` | An input the plan doesn't declare. `detail.suggestion` gives the closest declared name, when one is close enough ([syntax.md](syntax.md) SY-30). |
| `BK_INPUT_DUPLICATE` | The same input given twice. |
| `BK_INPUT_MISSING` | A required input without a value. `detail.command` is the exact command to run. |
| `BK_INPUT_EMPTY` | An empty value for a required input. |
| `BK_INPUT_INVALID` | A value that violates `in`/`matches` (`detail.constraint`) or the character rules. |
| `BK_INPUT_TOO_LARGE` | A value over 4 KiB or all values over 32 KiB. |

## 4. Plan errors

Plan errors carry a line and column. `detail.rule` is the ID of the rule that was broken (for example `RF-1`, `SY-56`), so new rules don't need new codes and every error points at its spec text ([ADR 0018](../adr/0018-review-semantics.md)). Which code applies ([ADR 0021](../adr/0021-wave-a-gaps.md)):

- **`BK_PLAN_UNKNOWN_KEY`**: a key that no kind or position accepts in that kind of mapping (a node, a condition, an input, `for:` …). A language key in the wrong place is not unknown.
- **`BK_PLAN_VALUE`**: anything one value decides alone: its grammar or type, an empty value or list, a regex outside the subset or that doesn't compile, a reserved prefix (`BLOKKY_`, a `BK_` user code). `detail.rule` names the rule.
- **`BK_PLAN_INVALID`**: a language key in the wrong place, and every rule relating keys, values or scopes. `detail.rule` names the rule.

One mistake is one error with one rule ([ADR 0025](../adr/0025-open-points.md)):

- The [reference.md §8](reference.md#8-rules-beyond-the-schema) rule is canonical: a rule elsewhere that restates it is reported as the `RF-n` rule.
- When no `RF-n` rule applies, the grammar or structure rule of [syntax.md](syntax.md) is reported: SY-52 for names, SY-53 for booleans, SY-54 for integers, SY-56 and SY-57 for durations, SY-20 for empty values, and so on. A rule elsewhere that restates it is reported as that `SY-n` rule: VA-4, VA-6, ER-1 and SY-42 as SY-52; SY-24 and CO-8 as SY-53; SY-25 as the grammar's rule; SY-41 as SY-20.
- A targeted error (SY-91) changes the message, not the rule: it carries the code and rule of the generic error it replaces. A string condition is reported as CO-4.
- Where §8 rules overlap, the more specific one wins: RF-4, RF-12, RF-28, RF-30, RF-31 and RF-32 over RF-3; RF-7 over RF-26 when an input or an enclosing scope is involved; RF-9 over RF-27 for `${…}` in a literal field; RF-6, RF-16 and RF-27 over RF-23, which is reported only when no more specific rule applies.
- A reference in a literal field (`{ var: X }`, as in `timeout: { var: X }`) is `BK_PLAN_INVALID` with RF-9 alone. A regex that doesn't compile is `BK_PLAN_VALUE` with RF-22. A root that is a list is `BK_PLAN_VALUE` with SY-32. A value of the wrong type for its field (a mapping where a list or scalar belongs, a scalar where a condition belongs, as in `retry: 3`) is `BK_PLAN_VALUE` with SY-88, the per-field table, unless a more specific rule names the mistake. `secret:` on an input is `BK_PLAN_UNKNOWN_KEY` with the targeted message (SY-48, SY-91). An image reference outside the OCI grammar is `BK_PLAN_VALUE` with SY-103; a missing `container.image` or mount `host` or `path` is `BK_PLAN_INVALID` with CP-40; a forbidden or reserved `container.env_pass` name, or one that is also in `env` or `export` on the node, is `BK_PLAN_INVALID` with RF-10 (CP-42) ([ADR 0026](../adr/0026-runtime-edge-cases.md)).
- A probe with both or neither of `exec:` and `script:`, or with `shell:` but no `script:`, is `BK_PLAN_INVALID` with rule CO-26; a node used as a condition is `BK_PLAN_INVALID` at its kind key ([ADR 0023](../adr/0023-wave-c-gaps.md)).

| Code | Meaning |
|---|---|
| `BK_PLAN_ENCODING` | Not UTF-8: a UTF-16/32 BOM or invalid UTF-8 ([syntax.md §2.2](syntax.md#22-encoding)). `detail.offset` for invalid UTF-8. |
| `BK_PLAN_CHARACTER` | A character rejected by the character lint. `detail.codepoint`, written `U+XXXX` (uppercase hex, at least four digits). |
| `BK_PLAN_TOO_LARGE` | Over 4 MiB, or nested deeper than 128 levels. |
| `BK_PLAN_YAML` | Not valid YAML, or a rejected YAML feature (anchor, alias, merge key, tag, directive, second document, complex key). |
| `BK_PLAN_DUPLICATE_KEY` | A key repeated in a mapping. |
| `BK_PLAN_UNKNOWN_KEY` | A key that no kind accepts in that kind of mapping (above). `detail.suggestion` from the synonym table or did-you-mean (SY-30). |
| `BK_PLAN_NOT_SUPPORTED` | A feature the implementation doesn't support yet. `detail.feature` is a feature id from the conformance vocabulary ([conformance/README.md §3.2](../conformance/README.md#32-features-and-requirements)). |
| `BK_PLAN_VERSION` | `blokky:` missing, malformed or naming an unsupported version. `detail.supported` lists the supported versions, always. |
| `BK_PLAN_VALUE` | A value that doesn't match its field's type or grammar (a boolean that isn't `true`/`false`, a bad duration, a bare number, an empty value or list, a regex outside the subset or that doesn't compile, a reserved prefix). `detail.rule`. |
| `BK_PLAN_INVALID` | A key in the wrong place, or a rule relating keys, values or scopes is violated. `detail.rule`. |

## 5. Node errors

"Retried" says whether `retry: true` retries the error ([reference.md §5.5](reference.md#55-what-retry-true-retries)); a `retry:` condition that matches the code can retry any node error except those marked "never".

### 5.1 Processes

| Code | Meaning | Retried |
|---|---|---|
| `BK_EXIT` | The leaf exited with a code that isn't 0 or in `ok_exit`. `detail.exit_code`. | yes |
| `BK_SIGNAL` | The leaf was killed by a signal it didn't get from Blokky (Unix). `detail.signal`: the signal's name (`SIGSEGV`). | yes |
| `BK_SPAWN_NOT_FOUND` | The program or shell couldn't be resolved; for a container leaf, argv[0] isn't in the image (CP-15). `detail.program`: argv[0] (or the shell) as written. | no |
| `BK_SPAWN_FAILED` | The OS refused to start the process (not executable, permission denied, a file format it can't run, a PowerShell execution policy or AppLocker rule that blocks the script). `detail.reason`: `not_executable`, `permission_denied`, `bad_format` or `blocked`. A literal argv[0] ending in `.bat` or `.cmd` is a plan error instead (`BK_PLAN_VALUE`, SH-10). | no |
| `BK_ENV_TOO_LARGE` | The leaf's environment or one value exceeds the OS limit. `detail.name`. | no |
| `BK_SHELL_UNAVAILABLE` | The `script` shell isn't supported on this OS or isn't configured (Git Bash on Windows), or, for a container leaf, isn't in the image (CP-15). | no |
| `BK_CWD_INVALID` | The node's cwd doesn't exist, isn't a directory or can't be entered. | no |
| `BK_TEMPDIR_FAILED` | The node's `tempdir` couldn't be created. | no |

### 5.2 Limits and cancellation

| Code | Meaning | Retried |
|---|---|---|
| `BK_TIMEOUT_TOTAL` | The node's own `timeout` (or `defaults.leaf_timeout`, except on repeating leaves, [ADR 0018](../adr/0018-review-semantics.md) S-9) fired. | never for the retrying node's own `timeout`; yes when a descendant's `timeout` fired inside an attempt (reference.md §5.5) |
| `BK_TIMEOUT_ATTEMPT` | The node's `attempt_timeout` fired for one attempt or iteration, or `defaults.leaf_timeout` did on a leaf with `retry`, `while` or `until`, where it limits each attempt. Leaves it stopped carry `killed_by: attempt_timeout`. | yes |
| `BK_TIMEOUT_FINALLY` | The node's `finally_timeout` fired: the running `finally` nodes were cancelled, their leaves with `killed_by: finally_timeout`. Attached to the node's error like any `finally` error (EM-7, EM-51; [ADR 0024](../adr/0024-wave-d-gaps.md)). | no |
| `BK_CANCELLED` | The node was cancelled from outside: a failing sibling, a decided `any`/`race`, an ancestor's limit, the `finally_timeout` of the `finally` list it is in, or the runtime stopping the run (run budget, shutdown; `detail.reason`). Its status is `cancelled`. | never |

### 5.3 Conditions, variables and captures

| Code | Meaning | Retried |
|---|---|---|
| `BK_CONDITION_ERROR` | A condition was neither true nor false ([conditions.md §7](conditions.md#7-condition-errors)). `detail.reason`: `undefined_variable`, `not_a_number`, `json_invalid`, `json_path`, `probe_exit`, `probe_timeout`, `probe_output_too_large`, `probe_spawn`, `output_too_large`, `output_encoding`, `path_access`; CO-38 gives the reason for each condition error (an unset environment variable is `undefined_variable`). In `assert`, `context` holds the assertion's `message` and `code`. | no |
| `BK_UNDEFINED_VARIABLE` | A display string or reference used a variable that isn't bound at that point. `detail.name`. | no |
| `BK_FROM_ENV_UNSET` | A `{ from_env: NAME }` names an unset environment variable. `detail.name`. | no |
| `BK_CAPTURE_TOO_LARGE` | stdout exceeded `max_capture_bytes`. | yes |
| `BK_CAPTURE_NUL` | stdout contained a NUL byte. | yes |
| `BK_CAPTURE_ENCODING` | stdout isn't valid in the leaf's `encoding`. | yes |
| `BK_CAPTURE_JSON` | A field capture's stdout isn't one valid JSON value. | yes |
| `BK_CAPTURE_PATH` | A field capture's JSON path doesn't resolve. `detail.path`: the path as written in the plan. | yes |

### 5.4 Explicit failures and aggregates

| Code | Meaning | Retried |
|---|---|---|
| `BK_FAIL` | A `fail` node without its own `code`. | no |
| `BK_ASSERT` | An `assert` whose condition was false, without its own `code`. | no |
| `BK_RETRIES_EXHAUSTED` | `retry` reached `max`; the last attempt's error is the cause. | no |
| `BK_LOOP_MAX_REACHED` | `while`/`until` reached `max` without the condition ending the loop; the last iteration's error, if any, is the cause. | no |
| `BK_ANY_ALL_FAILED` | Every child of an `any` failed; each child's error is a cause, in plan order. | yes if any cause is retried |
| `BK_FINALLY_FAILED` | The node's body succeeded but its `finally` failed; the `finally` error is the cause. (If the body failed, its error stays primary and the `finally` error is attached.) | no |
| `BK_GLOB_EMPTY` | A `for: { glob }` matched nothing and `allow_empty` isn't set. | no |
| `BK_ITEMS_TOO_MANY` | A `for` source produced more than `max_items` items (for `matrix`: combinations). | no |
| `BK_ITEMS_INVALID` | A `for: { items }` value isn't JSON, or its path doesn't select an array. | yes |

User codes from `fail` and `assert` (`code:`) are node errors too; `retry: true` doesn't retry them. The "Retried" column is the complete answer for `retry: true` ([reference.md §5.5](reference.md#55-what-retry-true-retries) summarizes it); a `retry:` condition can retry any code, except that the retrying node's own `timeout`, an ancestor's limit, cancellation and external stops are never retried.

### 5.5 Locks, containers and services

| Code | Meaning | Retried |
|---|---|---|
| `BK_LOCK_TIMEOUT` | A `lock` wasn't acquired within `wait`. | no |
| `BK_CONTAINER_FAILED` | The container couldn't be started, the image lacks `sh`, `sleep` or `kill` (CP-36; `detail.missing`: a list of the missing program names, such as `[kill]`), or the engine failed. `detail.engine`. | no |
| `BK_CWD_UNMAPPED` | The node's cwd maps through no container mount. | no |
| `BK_SERVICE_NOT_READY` | A service's `ready:` condition didn't hold within `ready_timeout`. `detail.service`. | yes |
| `BK_SERVICE_EXITED` | A service exited before it was ready, or (with `on_exit: fail`) after it was ready while the body ran; an exit after the body ended is recorded, not an error. `detail.service`, `detail.exit_code`. | yes |
