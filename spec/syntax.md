# Syntax

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document defines how a plan is written: encoding, the YAML subset, the root document, plan inputs, scalar grammars, how values reach fields (literals, references, interpolation), the per-field table, plain-scalar pitfalls and targeted errors. What each node and modifier *does* is in [reference.md](reference.md); terms are defined in the [glossary](glossary.md).

## 1. Conventions

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY and OPTIONAL are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when, they appear in all capitals.

- A **plan error** is detected before anything runs, and prevents the run. Every plan error carries a code from [errors.md](errors.md), a line and column, and, where this document says so, a corrected snippet.
- A **warning** points at something legal but likely wrong. Warnings never block a run by themselves; implementations decide how they are shown and whether users can tune them (for blokky-cli: lint rules).
- An implementation MUST report all plan errors it can find in one pass, not just the first.

## 2. Plan text

### 2.1 Sources

A plan is read from a file (`blokky run <path>`, conventionally `*.blokky.yaml` or `*.blokky.yml`) or from standard input. The agent convention for stdin is a bash heredoc with a quoted delimiter:

```bash
blokky run <<'BLOKKY_PLAN_EOF'
blokky: 1.0
exec: [git, status, --short]
BLOKKY_PLAN_EOF
```

The quoted delimiter stops the caller's shell from expanding `$X` and backticks in the plan. `blokky run` warns when a plan contains a line that looks like a heredoc delimiter. Invocation forms per platform are in the blokky-cli agent guide.

### 2.2 Encoding

- A plan MUST be UTF-8, with or without a byte-order mark (BOM). A UTF-8 BOM is ignored.
- A UTF-16 or UTF-32 BOM is a plan error whose message names the likely cause (PowerShell `Out-File` or `>` redirection) and the fix (`-Encoding utf8`, or the file form).
- Invalid UTF-8 is a plan error that gives the byte offset, line and column.
- Text that looks mangled by a lossy pipe (for example Windows PowerShell 5.1 replacing non-ASCII characters with `?`) SHOULD get a warning.

### 2.3 Size and depth caps

These caps are fixed by the spec, not configurable, so a plan is valid or invalid everywhere ([ADR 0007](../adr/0007-syntax-details.md)). They are checked before the syntax tree is built.

| Cap | Value |
|---|---|
| Plan size | 4 MiB (4 194 304 bytes), counted on the raw bytes |
| Nesting depth | 128 levels of YAML mappings and sequences |

### 2.4 Character lint

Before parsing, one pass over the decoded text, **comments and keys included**, checks every character:

- **Allowed control characters:** TAB (U+0009), LF (U+000A), and CR (U+000D) only when directly followed by LF.
- **Rejected:** every other C0 control character, DEL (U+007F) and C1 controls (U+0080–U+009F); bidirectional controls (U+061C, U+200E, U+200F, U+202A–U+202E, U+2066–U+2069); zero-width characters (U+200B–U+200D, U+2060) and U+FEFF anywhere except as a leading BOM.

Each rejected character is a plan error with its position and Unicode name. Hidden characters like these are how "Trojan Source" attacks make reviewed text differ from what runs, and comments are not exempt.

## 3. YAML subset

A plan is a YAML 1.2 document restricted as follows.

### 3.1 Rejected YAML features

Each of these is a plan error:

- anchors (`&a`), aliases (`*a`) and merge keys (`<<`);
- explicit tags (`!!str`, `!custom`) and directives (`%YAML`, `%TAG`);
- more than one document. A single leading `---` is allowed; a second `---` or a `...` followed by more content is an error;
- complex keys (the `?` indicator) and keys that aren't plain or quoted strings;
- **duplicate keys** in any mapping;
- **unknown keys** (§3.4);
- a key with no value (`timeout:` followed by nothing): an empty value is never "unset". Write `''` where an empty string is allowed;
- an empty list (`[]`), except in fields whose entry in the per-field table (§7) says an empty list is meaningful. Today only `mounts`;
- an empty mapping (`{}`).

### 3.2 Every scalar is a string

There is no implicit typing. YAML 1.1 and 1.2 type resolution doesn't apply: `on`, `yes`, `no`, `null`, `~`, `0x10`, `1e3` and `1.10` are all strings. Each field then parses its string with the grammar in §6:

- in a **boolean** field, the value MUST be exactly `true` or `false`; `True`, `yes`, `on` and `1` are plan errors with a fix-it;
- in an **integer**, **duration** or **size** field, the value MUST match that grammar;
- in a **string** field, any scalar is taken as written (`version: 1.10` is the string `1.10`, not the number 1.1).

Quoting changes nothing about the type: `max: '3'` and `max: 3` are the same.

### 3.3 Keys and order

- Keys are case-sensitive and lowercase (`timeout`, not `Timeout`). Variable names in keys (`env:`, `inputs:`, `capture:` mappings) follow their own grammar.
- Key order in a mapping has no meaning. For readability, plans SHOULD put `name` first, then the kind, then companion fields, then modifiers.

### 3.4 Unknown keys, did-you-mean and synonyms

An unknown key is a plan error. The message suggests the closest valid key at that position by edit distance, and also checks a synonym table for habits from other tools:

| Written | Suggestion |
|---|---|
| `register` | `capture` |
| `loop`, `with_items` | `for: { each: [...], as: ITEM }` |
| `retries` | `retry: true` plus `max: N` |
| `steps`, `tasks` | `do` |
| `run` | `script` (with `shell`) or `exec` |
| `continue-on-error` | `ignore_errors` |
| `timeout-minutes` | `timeout` (with a unit, e.g. `30m`) |
| `working-directory`, `working_dir` | `cwd` |
| `environment` | `env` |
| `enum`, `options`, `choices` (in an input) | `in` |
| `pattern`, `regex` (in an input) | `matches` |
| `desc`, `help` (in an input) | `description` |
| `value` (in an input) | `default` |
| `params`, `parameters`, `args`, `arguments`, `vars`, `variables` (at the root) | `inputs` |

A keyword of a feature the implementation doesn't support yet is not unknown: it is a plan error (`BK_PLAN_NOT_SUPPORTED`) that names the feature.

## 4. The plan document

### 4.1 Root

The root MUST be a single mapping. It holds the **plan-only keys** below plus exactly one **root node** (its kind and modifiers sit directly in the root mapping). A bare top-level list is a plan error whose fix-it wraps it in `do:`.

| Key | Required | Value |
|---|---|---|
| `blokky` | yes | The spec version, `MAJOR.MINOR` (§6.1). |
| `inputs` | no | Plan inputs (§5). |
| `outputs` | no | A list of variable names whose final values the run result returns. |
| `defaults` | no | A closed mapping: `shell`, `leaf_timeout`, `become`. |

Plan-only keys anywhere other than the root are plan errors ("`inputs:` is allowed only at the root").

```yaml
blokky: 1.0
name: build and test
defaults:
  shell: bash
  leaf_timeout: 10m
do:
  - exec: [dotnet, build, -c, Release]
  - exec: [dotnet, test, --no-build, -c, Release]
```

### 4.2 `blokky:`

- REQUIRED; a missing `blokky:` is a plan error with the fix-it `blokky: 1.0`.
- The value is the spec version the plan targets (§6.1). A version the implementation doesn't support is a plan error listing the supported versions.
- Spec patch releases never change the language, so plans never name a patch version.

### 4.3 `defaults:`

| Key | Meaning |
|---|---|
| `shell` | The shell for `script` leaves and script probes without their own `shell:` (before the implementation's configuration and detection). |
| `leaf_timeout` | A `timeout` for every `exec`/`script` leaf and probe that has none. Never applies to groups. |
| `become` | The user for every leaf and probe without its own `become` (a user name or `invoker`). |

Any other key under `defaults:` is a plan error. All `defaults` values are literal.

### 4.4 `outputs:`

A list of variable names (inputs, captures or tempdir paths in the plan's top-level scope). A name that is bound only inside a loop body is a plan error (unless gathered with `collect`). Semantics, including `null` for undefined outputs and the shape of secret outputs, are in [variables.md](variables.md).

## 5. Plan inputs

### 5.1 Shape

`inputs:` is a root-only mapping from input name to a mapping of these keys, all optional and all literal:

| Key | Value |
|---|---|
| `default` | The value used when the caller gives none. Its presence makes the input optional. |
| `description` | Display text for static views of the plan and the missing-input error. Never interpolated. Implementations MUST NOT show it where someone approves a run, because it can mislead. |
| `in` | A non-empty list of allowed values. |
| `matches` | A regex the whole value is searched with ([conditions.md](conditions.md), `matches`). |

```yaml
inputs:
  BRANCH:                                          # no default: required and non-empty
    description: Branch whose CI run to wait for
    matches: '^[A-Za-z0-9._/][A-Za-z0-9._/-]*$'    # also rules out a leading '-'
  ENVIRONMENT:
    default: staging
    in: [staging, production]
  NOTE:
    default: ''                                    # optional, may be blank
```

An input with no keys at all is written `NAME: { description: … }` or given a `default`; `NAME:` with no value is an empty value (§3.1).

### 5.2 Rules

- Input names follow the variable-name grammar (§6.2).
- **Strings only.** `default: 3` is the string `3`. There is no `type:` key.
- **Required is derived.** Without `default:` the input is required and its value MUST NOT be empty. There is no `required:` key.
- **At most one constraint:** `in:` or `matches:`, not both.
- **The `default` MUST satisfy the constraint.** A violation is a plan error.
- **Defaults are literal.** A reference (`default: { from_env: X }`) is a plan error.
- **No secret inputs.** `secret:` on an input is a plan error with a fix-it to `env: { X: { from_env: X, secret: true } }`.
- `description` MUST NOT contain `${`.
- Inputs bind into the plan scope that encloses the root node; they are used only through the variable forms of §7 and never reach literal fields.

How values are supplied, the value rules and the input error codes are in [variables.md §4](variables.md#4-plan-inputs).

## 6. Scalar grammars

### 6.1 Spec version

`^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`, for example `1.0`. Because every scalar is a string, `blokky: 1.10` is version 1.10, not 1.1.

### 6.2 Names

| Name | Grammar | Notes |
|---|---|---|
| Variable (input, capture, `as`, `tempdir.as`, `collect`) | `^[A-Z][A-Z0-9_]*$` | The `BLOKKY_` prefix is reserved. Derived names (`<AS>_INDEX`, `MATRIX_INDEX`) count as declarations. |
| Environment variable (`env:` keys, `from_env`, `env:` subject, `env_pass`) | `^[A-Za-z_][A-Za-z0-9_]*$` | Compared case-insensitively on Windows. Forbidden and reserved names: [variables.md](variables.md). |
| User error code (`fail`, `assert` `code:`) | `^[A-Z][A-Z0-9_]*$` | MUST NOT start with `BK_`. |
| Lock name, service name | `^[a-z0-9][a-z0-9._-]{0,63}$` | |
| User name (`become`, `container.user`) | literal string, or `invoker` (`become` only) | Checked against the OS at run time. |

### 6.3 Booleans

Exactly `true` or `false`. Unary condition operators (`empty: true`, `exists: true`) accept only `true`.

### 6.4 Integers

`^(0|[1-9][0-9]*)$`: decimal, no sign, no leading zeros, at most 2 147 483 647. Each field states its allowed range in [reference.md](reference.md) (for example `max` ≥ 1, `concurrency` ≥ 1).

**Decimals** (`backoff.factor`, `jitter`): `^(0|[1-9][0-9]*)(\.[0-9]+)?$`, no sign, no exponent, invariant culture. Each field states its range.

### 6.5 Durations

([ADR 0007](../adr/0007-syntax-details.md))

- One or more parts `<integer><unit>`, with units `h`, `m`, `s`, `ms`, in that (descending) order, each unit at most once, with no spaces: `500ms`, `10s`, `2m`, `1h30m`, `1m30s500ms`.
- Integers have no leading zeros and no sign; there are no fractions (`1500ms`, not `1.5s`) and no bare numbers (`timeout: 30` is a plan error with the fix-it `timeout: 30s`).
- A duration MUST be positive, except in fields that allow `0s` (`every`, `sleep`, `lock.wait`). Zero is written `0s`.
- The maximum is 168h (7 days).

### 6.6 Sizes

`<integer><unit>`, with units `B`, `KiB`, `MiB`, `GiB` (powers of 1024); for example `max_log_bytes: 100MiB`. There are no bare numbers and no decimal (`MB`) units.

### 6.7 Regular expressions

Regex values (`matches`, `not_matches`, input `matches`) use .NET syntax with `RegexOptions.NonBacktracking` and the invariant culture ([conditions.md](conditions.md)). A pattern that doesn't compile, or uses a construct NonBacktracking doesn't support (backreferences, lookaround, atomic groups), is a plan error. Patterns SHOULD be single-quoted (§8).

## 7. Values: literals, references and interpolation

### 7.1 Literals

Most fields are **literal**: the value is taken from the plan text as written. Literal fields never interpolate `${…}` and never accept a reference or an input. A `${` in a literal field is a plan error (§9). Executed text — `exec` strings, `script` text, probe commands — is always literal.

### 7.2 Whole-value references

Where a value affects execution and may come from a variable, the field accepts a **reference mapping** instead of a literal:

| Form | Meaning | Allowed in |
|---|---|---|
| `{ var: X }` | The value of plan variable `X`. | `exec` array elements (not argv[0]); `env` values; `cwd`; `path:` subjects; `stdin`; `stdin.file`; `mounts[].host`. |
| `{ from_env: NAME }` | The value of environment variable `NAME` in Blokky's own environment. | `env` values. |
| `stdin: { var: X }` | The variable's value as the leaf's stdin. | `stdin`. |
| `stdin: { file: P }` | The content of host file `P` (a literal path or `{ var: X }`). | `stdin`. |

- Any `var` or `from_env` reference MAY carry `secret: true`: `{ from_env: GH_TOKEN, secret: true }`. A literal can't be marked secret.
- A reference replaces the **whole** value. There is no string concatenation; a path is built by nesting relative `cwd` values (a relative child `cwd` resolves against the parent's cwd).
- argv[0] of an `exec` array MUST be a literal; a reference there is a plan error.
- Plan variables reach processes only through `env:`, `export:` and `exec` array elements; there is no other way.

### 7.3 Interpolation in display strings

`${X}` interpolation exists only in **display strings**: `name`, and the messages of `log`, `fail` and `assert` (`message:`).

- `${X}` is replaced by the value of plan variable `X`; process environment variables are never interpolated.
- `$${` produces a literal `${`.
- A `${X}` whose variable might be undefined is a warning; at run time an undefined variable is an error of the node.
- Non-scalar values (multi-field captures of objects or arrays) render as compact JSON; a `capture_file` variable renders as its path.
- Secret values are masked in the rendered text.

### 7.4 Per-field table

Legend: **L** = literal only; **`${}`** = display string with interpolation; **R** = literal or whole-value reference (forms in §7.2); **C** = a condition ([conditions.md](conditions.md)); **N** = a list of nodes. The type column refers to §6. Every field of the language is listed.

#### Root and inputs

| Field | Type | Form |
|---|---|---|
| `blokky` | spec version | L |
| `inputs.<NAME>.default` | string | L |
| `inputs.<NAME>.description` | string | L (never interpolated) |
| `inputs.<NAME>.in` | list of strings | L |
| `inputs.<NAME>.matches` | regex | L |
| `outputs` | list of variable names | L |
| `defaults.shell` | shell name | L |
| `defaults.leaf_timeout` | duration | L |
| `defaults.become` | user name or `invoker` | L |

#### Kinds and their companions

| Field | Type | Form |
|---|---|---|
| `exec` (array) | list of strings | element 0: L; other elements: R (`var` only) |
| `exec` (string) | string, split into argv | L |
| `script` | shell text | L |
| `shell` | shell name | L |
| `do`, `all`, `any`, `then`, `else` | list of nodes | N |
| `race` | list of nodes | N |
| `if` | condition | C |
| `sleep` | duration (`0s` allowed) | L |
| `log` | string | `${}` |
| `level` | `debug`, `info`, `warn` | L |
| `fail` | string | `${}` |
| `assert` | condition | C |
| `message` | string | `${}` |
| `code` | user error code | L |
| `concurrency` (`all`, `any`) | integer | L |
| `fail_fast` (`do`, `all`) | boolean | L |

#### Leaf options

| Field | Type | Form |
|---|---|---|
| `stdin` | string, `{ var }` or `{ file }` | R |
| `ok_exit` | list of integers | L |
| `stderr` | `merge` | L |
| `encoding` | encoding name | L |
| `max_log_bytes` | size | L |
| `keep_descendants` | boolean | L |
| `capture` | variable name, or mapping name → JSON path | L |
| `capture_file` | variable name | L |
| `secret` | boolean | L |

#### Modifiers

| Field | Type | Form |
|---|---|---|
| `name` | string | `${}` |
| `when` | condition | C |
| `timeout` | duration | L |
| `attempt_timeout` | duration | L |
| `tempdir` | `true`, or mapping | L |
| `tempdir.as` | variable name | L |
| `tempdir.prefix` | string | L |
| `cwd` | path | R (`var` only) |
| `env.<NAME>` | string, `{ var }`, `{ from_env }` | R |
| `export` | list of variable names | L |
| `finally` | list of nodes | N |
| `finally_timeout` | duration | L |
| `ignore_errors` | boolean | L |
| `retry` | `true` or condition | L / C |
| `while`, `until` | condition | C |
| `max` | integer | L |
| `every` | duration (`0s` allowed) | L |
| `on_body_failure` | `stop`, `continue` | L |
| `backoff.factor` | decimal, 1–10 | L |
| `backoff.max` | duration | L |
| `jitter` | decimal, 0 < j ≤ 1 | L |
| `lock` | lock name, or `{ name, wait }` | L |
| `lock.wait` | duration (`0s` allowed) | L |
| `container.image` | image reference | L |
| `container.mounts` | list of mounts (**empty list allowed**) | — |
| `container.mounts[].host` | path | R (`var` only) |
| `container.mounts[].path` | absolute container path | L |
| `container.mounts[].read_only` | boolean | L |
| `container.user` | user name | L |
| `container.env_pass` | list of environment variable names | L |
| `become` | user name or `invoker`, or `{ user }` | L |
| `services[]` fields | `name` (service name, required), `exec`/`script`, `shell`, `env`, `export`, `cwd` as for leaves and modifiers; `ready` C (required); `ready_timeout` duration L; `depends_on` list of service names L; `on_exit` `fail`/`ignore` L | as listed |

#### `for`

| Field | Type | Form |
|---|---|---|
| `for.each` | list of strings | L |
| `for.count` | integer | L |
| `for.glob` | glob pattern | L |
| `for.allow_empty` | boolean | L |
| `for.as` | variable name | L |
| `for.concurrency` | integer | L |
| `for.fail_fast` | boolean | L |
| `for.items` | `{ var, json }` | `var` names a variable; `json` L |
| `for.lines` | `{ var }` | `var` names a variable |
| `for.max_items` | integer (default 1000) | L |
| `for.fields` | mapping of variable name → JSON path | L |
| `for.keep_blank` | boolean | L |
| `for.matrix` | mapping of variable name → list of strings | L |
| `collect` | mapping capture name → list variable name | L |

#### Conditions

| Field | Type | Form |
|---|---|---|
| `var` | variable name | L |
| `env` (subject) | environment variable name | L |
| `path` | host path | R (`var` only) |
| `host` | `os`, `arch` | L |
| `result` | `stdout`, `stderr`, `exit`, `error` | L |
| `probe` | probe mapping | see below |
| `probe.exec`, `probe.script`, `probe.shell`, `probe.env`, `probe.export` | as for leaves | as for leaves |
| `probe.timeout` | duration | L |
| `probe.true_exit`, `probe.false_exit` | list of integers | L |
| `probe.timeout_result` | boolean | L |
| operator values (`equals`, `in`, `contains`, `matches`, `gt`, …) | string, list of strings, regex or number | L |
| `json` | JSON path | L |
| `ignore_case` | boolean | L |
| `port` | integer | L |
| `output` | `stdout`, `stderr` | L |

## 8. Plain-scalar pitfalls

YAML plain (unquoted) scalars have traps. Implementations MUST detect the cases below with the stated error or warning.

| Pitfall | Example | Result | Detection |
|---|---|---|---|
| A space then `#` starts a comment | `exec: echo done # tidy` | The command loses `# tidy`. | Warning when a comment follows an `exec`/`script` value on the same line. |
| `[` starts a flow sequence | `script: [ -f x ]` | `script` becomes a list. | Plan error with the fix-it `script: '[ -f x ]'` or a block scalar. |
| `[` in `exec` | `exec: [ -f x ]` | A valid argv array for `[`. | Warning that suggests `{ path: x, is_file: true }`. |
| A leading `"` | `exec: "a" b` | YAML parses a quoted scalar, then fails. | Plan error that explains the quoting. |
| Backslash escapes in double quotes | `matches: "^\d+$"` | `\d` is an invalid YAML escape. | Plan error with the fix-it `matches: '^\d+$'`. |
| Flow mappings with `,` `[` `]` `{` `}` | `{ probe: { exec: a,b } }` | The probe breaks apart. | Plan error that suggests a block mapping. |
| `script:` not a block scalar | `script: npm test && npm run lint` | Works, but fragile. | Warning. |

Plans and examples SHOULD use: plain scalars only for simple `exec` strings; `script:` text always as a `|` or `|-` block scalar; regexes always single-quoted; block mappings for non-trivial probes.

## 9. Targeted errors

Each of these plan errors names the problem and includes a corrected snippet. Codes are assigned in [errors.md](errors.md).

| Mistake | Fix-it |
|---|---|
| A mapping or a single node where a body list is expected (`do: { exec: … }`) | Prefix each node with a dash (`- exec: …`). |
| A string condition (`if: "$X == 1"`) | `if: { var: X, equals: '1' }` |
| GitHub-Actions-style `if:` next to another kind (`exec: …` plus `if: …`) | Use `when:` for a guard. |
| `${X}` in a literal or executed field | Use `{ var: X }` where references are allowed, nest a relative `cwd`, or `"$X"` in shell text with `export: [X]`. |
| `retry: 3` | `retry: true` plus `max: 3` |
| A bare number for a duration (`timeout: 30`) | `timeout: 30s` |
| A mapping as the value of `exec:`/`script:` (`exec: { cmd: …, timeout: 5m }`) | Move `timeout` (and other options) to the node level. |
| `not: { var: X, equals: a }` | `{ var: X, not_equals: a }` |
| Two kinds in one node | Split into two nodes in a `do:` list. |
| Two repetition modifiers in one node | Nest one node inside the other. |
| A secret literal (`env: { T: { value: abc, secret: true } }`) | Use `{ from_env: T, secret: true }`. |
| Input mistakes: `${{ inputs.X }}`, `{ var: inputs.X }`, `{ input: X }`, a lowercase name, `required:`, `type:`, `secret:`, a list form, `inputs:` below the root | The canonical `inputs:` mapping and `{ var: X }` usage (§5). |

## 10. Versioning

- A plan names the spec version it targets in `blokky:` (§4.2).
- Unknown keys are errors (§3.4), so an older implementation fails clearly on a plan that uses newer keys.
- An implementation that doesn't support a feature yet rejects every plan that uses it with `BK_PLAN_NOT_SUPPORTED` before anything runs ([errors.md](errors.md)).
- The plan schema (`schema/blokky.schema.json`) is normative for structure; its `$id` is versioned per spec release. Rules the schema can't express are listed in [reference.md](reference.md).
