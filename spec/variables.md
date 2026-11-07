# Variables

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is normative for plan variables: names, the kinds of bindings, plan inputs and their values, captures, scope and binding rules, how variables reach processes, the environment, outputs and secrets. How variable references are *written* (forms, the per-field table, interpolation syntax) is in [syntax.md §7](syntax.md#7-values-literals-references-and-interpolation). Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions). Rules carry IDs (`VA-n`) for conformance cases.

Where a rule here restates a rule of [reference.md §8](reference.md#8-rules-beyond-the-schema), a plan error reports the `RF-n` rule; where it restates only a grammar rule of [syntax.md](syntax.md), it reports that `SY-n` rule ([errors.md §4](errors.md#4-plan-errors)).

## 1. Two namespaces

- **VA-1.** **Plan variables** (bound by the plan) and **environment variables** (of processes) are separate namespaces. Nothing is exported implicitly: a plan variable reaches a process only through four routes: `env:` (`{ var: X }` as a value), `export: [X]`, a `{ var: X }` element of an `exec` array, or `stdin: { var: X }`. A `{ var: X }` in `cwd`, `stdin.file`, `path:` or `mounts[].host` chooses a location, it doesn't pass the value.
- **VA-2.** `${X}` in display strings and the `var:` condition subject resolve plan variables only. The `env:` condition subject and `{ from_env: NAME }` resolve environment variables only.
- **VA-3.** Every plan variable value is a string. A variable bound by `capture_file` holds a path.

## 2. Names

- **VA-4.** Plan variable names match `^[A-Z][A-Z0-9_]*$`. Names starting with `BLOKKY_` are reserved and can't be bound by a plan. A violation is reported as SY-52 ([syntax.md](syntax.md) SY-3).
- **VA-5.** Derived names count as declarations for every collision check: `<AS>_INDEX` for a `for` with `as: AS`, `MATRIX_INDEX` and the matrix keys for `matrix`.
- **VA-6.** Environment variable names match `^[A-Za-z_][A-Za-z0-9_]*$`. On Windows they are compared case-insensitively, including for collisions between `env` and `export` names. A name that doesn't match is reported as SY-52 ([syntax.md](syntax.md) SY-3).

## 3. Kinds of bindings

| Binding | Bound by | Value | Scope |
|---|---|---|---|
| Input | `inputs:` (root) | the caller's value or the default | the whole plan (plan scope) |
| Plan constant | `vars:` (root) | a literal, reference or template (§5.6) | the whole plan (plan scope) |
| Set variable | `set: { NAME: value }` | a literal, reference or template (§5.6) | like a capture (§6) |
| Capture | `capture: NAME` | the leaf's trimmed stdout | §6 |
| Field capture | `capture: { NAME: .path, … }` | a JSON field of stdout | §6 |
| File capture | `capture_file: NAME` | the absolute path of a file holding stdout | §6 |
| Loop item | `for: { …, as: NAME }` | the item | the loop body, per iteration |
| Loop index | `<AS>_INDEX`, `MATRIX_INDEX`; `index: NAME` on `retry`, `while`, `until` | the 0-based index (or from `start`) | the loop body and the node's condition, per iteration or attempt |
| Carried variable | `carry: { NAME: CAPTURE }` on `while`, `until` | `''` or `initial`, then the previous iteration's `CAPTURE` | the loop body and the node's condition, per iteration |
| Matrix key | `for: { matrix: { KEY: [...] } }` | the combination's value | the loop body, per iteration |
| Item field | `for: { items: …, fields: { NAME: .path } }` | a JSON field of the item | the loop body, per iteration |
| Temp dir | `tempdir: { as: NAME }` | the directory's absolute path | the node's body |
| Collected list | `collect: { CAPTURE: LIST }` on `for`, `while`, `until` | a JSON array of per-iteration values | like a capture of the loop node |

## 4. Plan inputs

The declaration syntax (`default`, `description`, `in`, `matches`) and its static rules are in [syntax.md §5](syntax.md#5-plan-inputs).

### 4.1 Plan scope

- **VA-7.** Inputs bind into the **plan scope**, which encloses the root node and is complete before anything runs. Root modifiers (`name`, `when`, `cwd`, `env`) may use them.
- **VA-8.** Inputs are always defined: a required input has a non-empty value, and an optional one has its value or its default.
- **VA-9.** No other binding may reuse an input's name; the error names the input and its declaration line. This holds in `any` children too.
- **VA-10.** Inputs are used only through the variable forms (`{ var: X }`, `export`, `${X}`, the `var:` subject, `outputs`) and never reach literal fields. `host:` stays the only statically pruned subject; inputs never prune branches, and a required input stays required even if only a pruned branch uses it.

### 4.2 Values

- **VA-11.** Values are supplied by whoever starts the run, as name/value pairs, before it starts (for blokky-cli: `--input NAME=VALUE` or the MCP `inputs` object). They never come from the environment, configuration or the plan itself, and missing inputs are never prompted for.
- **VA-12.** An explicit value beats the default, including an empty one: `--input NOTE=` gives `''`. An empty value for a required input is `BK_INPUT_EMPTY`.
- **VA-13.** A value MUST NOT contain NUL, any C0 or C1 control character except TAB (CR and LF included), bidirectional or zero-width characters, or U+FFFD. Multi-line data belongs in the plan or a file.
- **VA-14.** A value is at most 4 KiB and all values together at most 32 KiB, in UTF-8 bytes; larger values are rejected with `BK_INPUT_TOO_LARGE` ([ADR 0007](../adr/0007-syntax-details.md), [ADR 0021](../adr/0021-wave-a-gaps.md)).
- **VA-15.** MCP values MUST be JSON strings; numbers, booleans, `null` and duplicate keys are rejected, with no coercion.
- **VA-16.** A value is checked against its constraint with condition semantics (`in`: exact string match; `matches`: unanchored search with the portable regex subset, no trimming).

### 4.3 Input errors

All input errors are found and reported together, before anything runs (EM-1).

| Code | Cause |
|---|---|
| `BK_INPUT_SYNTAX` | A malformed `--input`: no `=`, or a name that breaks the name grammar (SY-52 allows only `[A-Za-z0-9_]`, so `my-input` is a syntax error; `branch` is well-formed and unknown). |
| `BK_INPUT_UNKNOWN` | A name the plan doesn't declare; `detail.suggestion` gives the closest declared name by SY-30's rule (`branch` → `BRANCH`, `BRANCHH` → `BRANCH`). |
| `BK_INPUT_DUPLICATE` | The same name given twice. |
| `BK_INPUT_MISSING` | A required input without a value; the message prints the exact command to run. |
| `BK_INPUT_EMPTY` | An empty value for a required input. |
| `BK_INPUT_INVALID` | A value that violates `in`/`matches` (the message quotes the constraint) or the character rules. |
| `BK_INPUT_TOO_LARGE` | A value or the total over the cap. |

Static views of a plan (for review, before a run) MAY accept a missing required input and show it as a placeholder; unknown and duplicate inputs are still errors there.

## 5. Captures, `set` and `vars`

### 5.1 Forms

```yaml
- exec: [gh, run, list, -b, { var: BRANCH }, -L1, --json, databaseId, -q, '.[0].databaseId']
  capture: RUN_ID                          # trimmed stdout
- exec: [gh, pr, view, --json, 'number,state']
  capture: { PR: .number, STATE: .state }  # JSON fields of stdout
- exec: [dotnet, list, package, --format, json]
  capture_file: PACKAGES                   # path of a file holding stdout
```

- **VA-17.** `capture` and `capture_file` are valid only on `exec` and `script` nodes. A node may have one `capture` (either form) and one `capture_file`.
- **VA-18.** Captures are evaluated after the leaf completes and **bound only if the node succeeds** (exit 0 or in `ok_exit`). A node whose failure is ignored binds nothing. The one exception is `collect`, which binds its list also when the loop fails (VA-55).
- **VA-19.** With `stderr: merge`, the captured text includes stderr.

### 5.2 Text captures

- **VA-20.** `capture: NAME` binds stdout decoded with the leaf's `encoding` (default UTF-8), with **every trailing `\n` and `\r` removed** after decoding ([ADR 0002](../adr/0002-language-core.md)). Nothing else is trimmed.
- **VA-21.** The capture fails the node, with a distinct code, if stdout:
  - is larger than `max_capture_bytes` (default 1 MiB; the message suggests `capture_file`);
  - contains U+0000 after decoding (so UTF-16 output can be captured);
  - isn't valid in the leaf's `encoding` (the message suggests `encoding:` or `capture_file`). Captured values are never silently altered ([ADR 0010](../adr/0010-variables-details.md)).

### 5.3 Field captures

- **VA-22.** `capture: { NAME: PATH, … }` parses stdout as **one JSON value**, after the checks of VA-21 in their order, and binds each name to the value at its JSON path ([syntax.md](syntax.md); `.`, `.name`, `.["key"]`, `[N]`). Output that isn't valid JSON fails the node.
- **VA-23.** Values are converted to strings:

| JSON value | Bound string |
|---|---|
| string | its content (unescaped) |
| number | its text as written in the output |
| `true`, `false` | `true`, `false` |
| `null` | `''` (empty) |
| object, array | compact JSON text |

- **VA-24.** A path that doesn't resolve (a missing key, an index out of range, a key on a non-object) fails the node with a distinct missing-path code. The same conversion applies to `json:` in conditions, where a missing path is a condition error.

### 5.4 File captures

- **VA-25.** `capture_file: NAME` writes stdout's raw bytes (not decoded, not trimmed) to a file owned by the run (readable only by the run's user) and binds its absolute path. `max_capture_bytes` doesn't apply.
- **VA-26.** The file outlives the node and the run, but it belongs to the run: the implementation may remove it later (for blokky-cli: `blokky clean`). A plan that needs it afterwards copies or moves it.

### 5.5 Secret captures

- **VA-27.** `secret: true` on the node marks the variables bound by its `capture` (both forms) as secret. A `capture_file` path is never secret, and the file's content is stored as written, not masked.

### 5.6 `set` and `vars`

([ADR 0015](../adr/0015-set-and-vars.md))

- **VA-56.** A `set` or `vars` value is a literal, a whole-value reference (`{ var: X }`, `{ from_env: NAME }`, optionally `secret: true`), or a **template**: a string containing `${X}` placeholders, with the display-string syntax ([syntax.md §7.3](syntax.md#73-interpolation-in-display-strings-and-templates)). A literal without `${` is a plain string.
- **VA-57.** Templates join strings only: `${X}` is replaced by `X`'s value, `$${` produces `${`. There are no functions. Templates appear in `set` and `vars` values and nowhere else in executed fields. A template result passed as code (to `bash -c`, `python -c`, `node -e`, `eval`, an interpreter's stdin) is string interpolation into code, with the same injection risk as unquoted interpolation in bash; the safe pattern is `script` with `export`. Static views SHOULD show the template and the source of each placeholder for a variable in such a position ([reference.md §9](reference.md#9-security-considerations)).
- **VA-58.** An undefined variable in a template or reference fails the `set` node with `BK_UNDEFINED_VARIABLE` (a plan error for `vars`, and for references the scope check rules out, VA-38); an unset `from_env` fails with `BK_FROM_ENV_UNSET` (VA-40).
- **VA-59.** A value is secret if it is a secret reference or a template that uses any secret variable.
- **VA-60.** `set` entries are bound in order, so a later entry may use an earlier one; the bindings are scoped like a capture of the `set` node (§6).
- **VA-61.** `vars` entries are bound in the plan scope, in order, after the inputs and before anything runs. Their values may use only inputs, earlier `vars` entries and `from_env`; never a value produced by running something. The caller can't override them.

## 6. Scope and binding

- **VA-28.** **Sequences.** In `do`, a capture is visible to later siblings, their descendants and, after the `do`, to the `do`'s later siblings.
- **VA-29.** **Parallel children.** Two `all` children MUST NOT bind the same name anywhere in their subtrees. A binding of an `all` child is visible after the `all` completes.
- **VA-30.** **`any` and `race`.** Only the deciding child's captures are bound. Different children MAY capture the same name (never an input's name).
- **VA-31.** **Branches.** A name bound (by `set` or a capture) in **both** `then` and `else` of an `if`, or by **every** child of an `any` or `race`, is definitely bound after the node succeeds. Bound in only some branches or children, it is *possibly undefined* afterwards; using it without a `defined` check SHOULD get a warning ([ADR 0015](../adr/0015-set-and-vars.md)).
- **VA-32.** **Repetition on the node itself.** A capture on a node with `retry`, `while` or `until` is visible to that attempt's own condition (for a failed attempt, the capture is evaluated best effort for the `retry` condition only: one that can't be evaluated leaves the name undefined and doesn't change the attempt's error) and is **published** to the enclosing scope from the terminating attempt, only if the node succeeds.
- **VA-33.** **Loop bodies.** Captures of nodes inside a `while`, `until` or `for` body are scoped to the iteration: later nodes in the same iteration see them, the next iteration's condition sees them (`while`, `until`), but they are never published outside the loop. The next iteration's body sees a value of the previous one only through `carry` (VA-62). The first `while` check sees only the enclosing scope; a `while` condition that reads a body capture without `defined` gets a lint warning.
- **VA-34.** **Loop iterations never publish.** Values leave a `for`, `while` or `until` body only through `collect`, in item or iteration order, with `null` for failed or skipped iterations.
- **VA-54.** **Item fields.** `fields` binds its variables per iteration, like `as`, with the conversion of VA-23; they count as declarations for collision and shadowing checks.
- **VA-55.** **`collect`.** The list variable is bound after the loop, in the loop node's enclosing scope like a capture of the node, as a compact JSON array of strings with `null` entries for iterations that failed, were skipped or cancelled, or didn't bind the capture. It is bound **also when the loop fails**, an exception to VA-18, so summaries after a partial failure work ([ADR 0018](../adr/0018-review-semantics.md)). Items are strings: a JSON capture is collected as its JSON text. The list is secret if the collected capture is secret.
- **VA-35.** **`finally`.** `finally` nodes see everything the body bound. Captures under `finally` are visible only to later nodes in the same `finally` list and their descendants; referencing one outside is a plan error ([ADR 0002](../adr/0002-language-core.md), Q-s).
- **VA-36.** **Single assignment.** Binding a name that is already bound is a plan error: in an enclosing scope (shadowing, including loop variables, tempdir names, inputs and `vars`), or earlier in the same scope (two sequential siblings, or a `set` of a bound name). Alternatives (`if` branches, `any`/`race` children) may bind the same name, because only one of them runs to completion.
- **VA-37.** **Own variables.** The modifiers outside repetition (`when`, `timeout`, `lock`, `tempdir`, `cwd`, `env`, `container`, `services`) MUST NOT reference variables the node itself introduces (`as`, `tempdir.as`, `index`, `carry`, its own captures). The error says "move it into the body".
- **VA-62.** **`carry`.** `carry: { NAME: CAPTURE }` on a `while` or `until` node binds `NAME` at the start of every iteration: to `''` (or the long form's `initial`) in the first, and to the value `CAPTURE` had at the end of the previous iteration afterwards. `NAME` is bound once per iteration, so single assignment holds (VA-36); it is visible in the body and in the node's condition, never published, and secret if `CAPTURE` is. If the previous iteration didn't bind `CAPTURE` (its body failed under `on_body_failure: continue`, or a `return` came first), `NAME` keeps the value it had in that iteration, so a failed page is fetched again ([ADR 0017](../adr/0017-review-features.md)).
- **VA-63.** **`index`.** `index: NAME` on a `retry`, `while` or `until` node binds the attempt or iteration number: 0 for the first, or `start` with `{ as: NAME, start: N }`. It is visible in the body and in the node's condition, and never published.
- **VA-38.** **Undefined variables.** Before the run, implementations do a **syntactic scope check**: a reference is a plan error only if no binding of that name can come before it (a typo, a name bound only in an unrelated branch or later in the plan, a capture used before its node, a `finally` capture used outside its list). Whether a possible binding actually happened is checked at run time: an unbound reference is a condition error in conditions and `BK_UNDEFINED_VARIABLE` in display strings, templates and references. Beyond VA-31's SHOULD, warnings about possibly undefined references are optional, so every implementation reports the same plan errors ([ADR 0018](../adr/0018-review-semantics.md)).

## 7. Environment

### 7.1 A leaf's environment

- **VA-39.** A leaf's environment is Blokky's own environment, overlaid by the output defaults Blokky sets (`NO_COLOR`, `TERM`, VA-44), then by the `env` and `export` mappings of every enclosing node from the root down (inner wins), then by the `BLOKKY_*` variables (VA-44). `BASH_ENV` and `ENV` are then removed.
- **VA-40.** `{ from_env: NAME }` reads the environment the run started with. Because that is known before anything runs, `from_env` values are treated like inputs: they are resolved in the validation phase, and static views show each value next to the inputs (masked when the reference is secret), or that it is unset. An unset `NAME` fails with `BK_FROM_ENV_UNSET` where it is used: in validation for `vars`, which bind before anything runs (reported with the plan errors, at the environment variable name, [syntax.md](syntax.md) SY-1), and otherwise when the node that uses it runs, so a reference guarded by `when: { env: NAME, defined: true }` stays valid ([ADR 0018](../adr/0018-review-semantics.md)).

### 7.2 Forbidden and reserved names

- **VA-41.** `env` MUST NOT set `PATH`, `BASH_ENV`, `ENV`, `SHELLOPTS` or `BASHOPTS` (plan error).
- **VA-42.** `export` MUST NOT name a reserved environment name: `PATH`, `HOME`, `USER`, `SHELL`, `IFS`, `PWD`, `TMP`, `TMPDIR`, `TEMP`, names starting with `TMP`, `LD_*`, `DYLD_*`, `BASH_ENV`, `ENV`, `PS1`–`PS4` and other `PS*`, `PATHEXT`, `COMSPEC`, `SystemRoot`, `BLOKKY_*`, or an execution-influencing name (§7.3). Setting one deliberately needs an explicit `env` entry.
- **VA-43.** A name in both `env` and `export` on the same node is a plan error.

### 7.3 Execution-influencing variables

Setting these changes what a program loads or runs. Setting one through `env` is statically visible, so implementations can flag it for review (for blokky-cli: `exec_env_risk` in [`leaves`](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/leaves-and-validation.md)):

`LD_*`, `DYLD_*`, `BASH_FUNC_*`, `NODE_OPTIONS`, `NODE_PATH`, `PYTHONPATH`, `PYTHONSTARTUP`, `PYTHONHOME`, `PERL5OPT`, `PERL5LIB`, `RUBYOPT`, `RUBYLIB`, `JAVA_TOOL_OPTIONS`, `JDK_JAVA_OPTIONS`, `_JAVA_OPTIONS`, `DOTNET_STARTUP_HOOKS`, `DOTNET_ADDITIONAL_DEPS`, `CORECLR_PROFILER*`, `COR_PROFILER*`, `GIT_SSH_COMMAND`, `GIT_SSH`, `GIT_CONFIG_*`, `GIT_EXEC_PATH`, `GIT_ASKPASS`, `SSH_ASKPASS`, `GIT_PROXY_COMMAND`, `GIT_EXTERNAL_DIFF`, `DOCKER_HOST`, `DOCKER_CONFIG`, `KUBECONFIG`.

`npm_config_*`, `PSModulePath`, `PAGER`, `GIT_PAGER`, `EDITOR`, `VISUAL`, `PERL5DB`, `R_PROFILE`, `R_PROFILE_USER`, and names ending in `_OPTIONS`.

The list is illustrative, not exhaustive: almost any environment variable can change what some program does. Flagging is a review aid (hygiene), not a control; every `env` entry is shown in static views anyway. The list is versioned with the spec; adding a name is a non-breaking change.

### 7.4 Variables Blokky sets

- **VA-44.** Every leaf gets:
  - `BLOKKY_RUN_ID`, the run's id. Implementations MAY set further `BLOKKY_*` variables for their own needs (for blokky-cli: `BLOKKY_MAX_DURATION`, the remaining run budget for nested runs). Plans can't set `BLOKKY_*` names, and these variables override the plan's mappings.
  - `NO_COLOR=1`, and `TERM=dumb` when the environment the run started with has no `TERM`, so that programs don't write colour codes into captured output: leaves have no terminal, but many programs (PowerShell among them) decide by `TERM` alone ([ADR 0027](../adr/0027-spike-findings.md)). These are defaults below the plan's mappings: `env` (or `export`) can override either, for example `env: { TERM: xterm-256color, NO_COLOR: '' }` for a program whose coloured output is wanted. Neither name is forbidden (VA-41) or reserved (VA-42).

## 8. Outputs

- **VA-45.** `outputs: [NAME, …]` at the root returns the final value of each listed variable in the run result's outputs ([results.md](results.md)). Inputs may be listed.
- **VA-46.** A listed variable that is unbound at the end of the run has no value (`null`).
- **VA-47.** A secret variable is marked as secret, without its value (never a masked value). Masking follows the value, not the variable (VA-51): a non-secret output whose value contains a secret value shows it masked.
- **VA-48.** A variable bound only inside a loop body can't be an output (plan error, unless gathered with `collect`). A `capture_file` output is the path.

## 9. Secrets

### 9.1 Sources

- **VA-49.** Secrets come **only by reference**: `{ from_env: NAME, secret: true }`, `{ var: X, secret: true }`, or captures of a node with `secret: true`. Marking a literal as secret is a plan error. There are no secret inputs.
- **VA-50.** Secret-ness follows the variable: a variable bound from a secret source is secret wherever it is used, and so is every value derived from one: a template using it (VA-59), `for` items, `fields` and matrix values from it, a `json:` extraction of it, a `carry` of it and a `collect` list of it. Iteration items from a secret source are recorded masked.

### 9.2 Masking

- **VA-51.** Every secret value of at least **6 characters** MUST be replaced with `***` in everything an implementation shows, keeps or passes on about a run: displayed and stored output, the run result, rendered display strings, and data handed to other tools. Output MUST be masked even when a value is split across chunks.
- **VA-52.** A secret shorter than 6 characters isn't masked; the implementation warns, naming the reference (never the value) ([ADR 0010](../adr/0010-variables-details.md)).
- **VA-53.** Static views of a plan never show a secret value; they show the source, for example `TOKEN ← env GH_TOKEN (secret)`. Non-secret `from_env` values are shown resolved (VA-40).

### 9.3 Limits

Masking is hygiene, not secrecy. It matches exact values only and doesn't follow derived or transformed values (base64, substrings, URL encoding). A process that receives a secret can print or send it anywhere. Conditions on secrets act as oracles: `matches` or `gt` on a secret leaks information through the condition result. Implementations SHOULD warn about inputs with secret-looking names (`*TOKEN*`, `*SECRET*`, `*PASSWORD*`, `*_KEY`), because input values appear in the run result verbatim. A secret in an `exec` element is on the process's command line, readable by other local users and by audit logs; pass secrets through `env` or `stdin` instead. Implementations SHOULD warn about a secret reference in an `exec` element.
