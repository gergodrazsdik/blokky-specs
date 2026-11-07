# Syntax

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document defines how a plan is written: encoding, the YAML subset, the root document, plan inputs, scalar grammars, how values reach fields (literals, references, interpolation), the per-field table, plain-scalar pitfalls and targeted errors. What each node and modifier *does* is in [reference.md](reference.md); terms are defined in the [glossary](glossary.md). Rules carry IDs (`SY-n`) for conformance cases and for `detail.rule` ([ADR 0018](../adr/0018-review-semantics.md)); IDs of removed rules are not reused.

## 1. Conventions

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY and OPTIONAL are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when, they appear in all capitals.

- **SY-1.** A **plan error** is detected before anything runs, and prevents the run. Every plan error carries a code from [errors.md](errors.md), a line and column (of the offending key, or of its value when the value is what is wrong; for a missing key, of the key that requires it, such as `until` for a missing `max` or `timeout` (RF-5) or `if` for a missing `then`, or, when no key requires it, of the mapping that lacks it), and, where this document says so, a corrected snippet. Lines are counted from 1 and end at LF, CRLF or a lone CR; columns are 1-based code points, and a UTF-8 BOM isn't counted. A quoted scalar is located at its opening quote, and an error inside a string value (a `${X}`, a regex) at the value's start. A missing value is located at its key. When two keys conflict, the later one in document order is reported. Errors about the whole text (encoding, size) are at line 1, column 1; the depth error is at the first node that is too deep ([ADR 0021](../adr/0021-wave-a-gaps.md)).
- **SY-2.** A **warning** points at something legal but likely wrong. Warnings never block a run by themselves; implementations decide how they are shown and whether users can tune them (for blokky-cli: lint rules).
- **SY-3.** An implementation MUST report all plan errors it can find in one pass, not just the first. One mistake is one error: a rule here that restates a rule of [reference.md §8](reference.md#8-rules-beyond-the-schema) is reported as that `RF-n` rule ([errors.md §4](errors.md#4-plan-errors)), and a targeted error (SY-91) replaces the generic error for the same mistake.

## 2. Plan text

### 2.1 Sources

**SY-4.** A plan is read from a file (`blokky run <path>`, conventionally `*.blokky.yaml` or `*.blokky.yml`) or from standard input. The agent convention for stdin is a bash heredoc with a quoted delimiter:

```bash
blokky run <<'BLOKKY_PLAN_EOF'
blokky: 1.0
exec: [git, status, --short]
BLOKKY_PLAN_EOF
```

The quoted delimiter stops the caller's shell from expanding `$X` and backticks in the plan. `blokky run` warns when a plan contains a line that looks like a heredoc delimiter. Invocation forms per platform are in the blokky-cli agent guide.

### 2.2 Encoding

- **SY-5.** A plan MUST be UTF-8, with or without a byte-order mark (BOM). A UTF-8 BOM is ignored.
- **SY-6.** A UTF-16 or UTF-32 BOM is a plan error, the only one reported for that text, whose message names the likely cause (PowerShell `Out-File` or `>` redirection) and the fix (`-Encoding utf8`, or the file form).
- **SY-7.** Invalid UTF-8 is one plan error, at the first invalid byte, that gives its byte offset (`detail.offset`), line and column.
- **SY-8.** Text that looks mangled by a lossy pipe (for example Windows PowerShell 5.1 replacing non-ASCII characters with `?`) SHOULD get a warning.

### 2.3 Size and depth caps

**SY-9.** These caps are fixed by the spec, not configurable, so a plan is valid or invalid everywhere ([ADR 0007](../adr/0007-syntax-details.md)). They are checked before the syntax tree is built.

| Cap | Value |
|---|---|
| Plan size | 4 MiB (4 194 304 bytes), counted on the raw bytes |
| Nesting depth | 128 levels of YAML mappings and sequences |

### 2.4 Character lint

**SY-10.** Before parsing, one pass over the decoded text, **comments and keys included**, checks every character. Errors from this pass end processing: the text isn't parsed as YAML, so no `BK_PLAN_YAML` follows them.

- **SY-11.** **Allowed control characters:** TAB (U+0009), LF (U+000A), and CR (U+000D) only when directly followed by LF.
- **SY-12.** **Rejected:** every other C0 control character, DEL (U+007F) and C1 controls (U+0080–U+009F); bidirectional controls (U+061C, U+200E, U+200F, U+202A–U+202E, U+2066–U+2069); zero-width characters (U+200B–U+200D, U+2060) and U+FEFF anywhere except as a leading BOM.

**SY-13.** Each rejected character is a plan error with its position and Unicode name. Hidden characters like these are how "Trojan Source" attacks make reviewed text differ from what runs, and comments are not exempt.

## 3. YAML subset

A plan is a YAML 1.2 document restricted as follows.

### 3.1 Rejected YAML features

Each of these is a plan error:

- **SY-14.** anchors (`&a`), aliases (`*a`) and merge keys (`<<`);
- **SY-15.** explicit tags (`!!str`, `!custom`) and directives (`%YAML`, `%TAG`);
- **SY-16.** more than one document. A single leading `---` is allowed; a second `---` or a `...` followed by more content is an error;
- **SY-17.** complex keys (the `?` indicator) and keys that aren't plain or quoted strings;
- **SY-18.** **duplicate keys** in any mapping;
- **SY-19.** **unknown keys** (§3.4);
- **SY-20.** a key with no value (`timeout:` followed by nothing): an empty value is never "unset". Write `''` where an empty string is allowed;
- **SY-21.** an empty list (`[]`), except in fields whose entry in the per-field table (§7) says an empty list is meaningful. Today only `mounts`;
- **SY-22.** an empty mapping (`{}`).

### 3.2 Every scalar is a string

**SY-23.** There is no implicit typing. YAML 1.1 and 1.2 type resolution doesn't apply: `on`, `yes`, `no`, `null`, `~`, `0x10`, `1e3` and `1.10` are all strings. Each field then parses its string with the grammar in §6:

- **SY-24.** in a **boolean** field, the value MUST be exactly `true` or `false`; `True`, `yes`, `on` and `1` are plan errors with a fix-it;
- **SY-25.** in an **integer**, **duration** or **size** field, the value MUST match that grammar;
- **SY-26.** in a **string** field, any scalar is taken as written (`version: 1.10` is the string `1.10`, not the number 1.1).

**SY-27.** Quoting changes nothing about the type: `max: '3'` and `max: 3` are the same.

### 3.3 Keys and order

- **SY-28.** Keys are case-sensitive and lowercase (`timeout`, not `Timeout`). Variable names in keys (`env:`, `inputs:`, `capture:` mappings) follow their own grammar.
- **SY-29.** Key order in a mapping has no meaning. For readability, plans SHOULD put `name` first, then the kind, then companion fields, then modifiers.

### 3.4 Unknown keys, did-you-mean and synonyms

**SY-30.** An unknown key is a plan error. The message suggests the closest valid key at that position by edit distance, and also checks a synonym table for habits from other tools. **Closest** means the smallest edit distance (Levenshtein, over code points) between the names after simple uppercase mapping (as in CO-12), at most 2; ties go to the name listed first (declaration order for inputs; for keys, the order of the schema's `properties` for that mapping, whose candidates are every key valid in it). When a close name or a synonym exists, `detail.suggestion` MUST give it (a synonym first; for a synonym whose suggestion has several parts, such as `loop`, the key it names, `for`, with the rest in the message); otherwise it is absent. The same rule applies to unknown inputs (`BK_INPUT_UNKNOWN`).

| Written | Suggestion |
|---|---|
| `register` | `capture` |
| `loop`, `with_items` | `for: { each: [...], as: ITEM }` |
| `retries` | `retry: true` plus `max: N+1` (`max` counts attempts, including the first) |
| `steps`, `tasks` | `do` |
| `run` | `script` (with `shell`) or `exec` |
| `continue-on-error` | `ignore_errors` |
| `exit`, `continue`, `break` | `return` (ends the enclosing sequence; there is no `break`) |
| `timeout-minutes` | `timeout` (with a unit, e.g. `30m`) |
| `working-directory`, `working_dir` | `cwd` |
| `environment` | `env` |
| `enum`, `options`, `choices` (in an input) | `in` |
| `pattern`, `regex` (in an input) | `matches` |
| `desc`, `help` (in an input) | `description` |
| `value` (in an input) | `default` |
| `params`, `parameters`, `args`, `arguments` (at the root) | `inputs` |
| `variables`, `constants` (at the root) | `vars` |

**SY-31.** A keyword of a feature the implementation doesn't support yet is not unknown: it is a plan error (`BK_PLAN_NOT_SUPPORTED`) that names the feature.

## 4. The plan document

### 4.1 Root

**SY-32.** The root MUST be a single mapping. It holds the **plan-only keys** below plus exactly one **root node** (its kind and modifiers sit directly in the root mapping). A bare top-level list is a plan error whose fix-it wraps it in `do:`.

| Key | Required | Value |
|---|---|---|
| `blokky` | yes | The spec version, `MAJOR.MINOR` (§6.1). |
| `inputs` | no | Plan inputs (§5). |
| `vars` | no | Plan constants: a mapping of variable names to values (literals, references, templates; [variables.md §5.6](variables.md#56-set-and-vars)). |
| `outputs` | no | A list of variable names whose final values the run result returns. |
| `defaults` | no | A closed mapping: `shell`, `leaf_timeout`. |

**SY-33.** Plan-only keys anywhere other than the root are plan errors ("`inputs:` is allowed only at the root").

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

- **SY-34.** REQUIRED; a missing `blokky:` is a plan error with the fix-it `blokky: 1.0`.
- **SY-35.** The value is the spec version the plan targets (§6.1). A version the implementation doesn't support is a plan error listing the supported versions.
- **SY-36.** Spec patch releases never change the language, so plans never name a patch version.

### 4.3 `defaults:`

**SY-37.** `defaults:` is a closed mapping with these keys:

| Key | Meaning |
|---|---|
| `shell` | The shell for `script` leaves and script probes without their own `shell:` (before the implementation's configuration and detection). |
| `leaf_timeout` | A `timeout` for every `exec`/`script` leaf and probe that has none. Never applies to groups. |

**SY-38.** Any other key under `defaults:` is a plan error. All `defaults` values are literal.

### 4.4 `outputs:`

**SY-39.** A list of variable names (inputs, `vars`, `set` variables, captures or tempdir paths in the plan's top-level scope). A name that is bound only inside a loop body is a plan error (unless gathered with `collect`). Semantics, including `null` for undefined outputs and the shape of secret outputs, are in [variables.md](variables.md).

## 5. Plan inputs

### 5.1 Shape

**SY-40.** `inputs:` is a root-only mapping from input name to a mapping of these keys, all optional and all literal:

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

**SY-41.** An input with no keys at all is written `NAME: { description: … }` or given a `default`; `NAME:` with no value is an empty value (§3.1).

### 5.2 Rules

- **SY-42.** Input names follow the variable-name grammar (§6.2).
- **SY-43.** **Strings only.** `default: 3` is the string `3`. There is no `type:` key.
- **SY-44.** **Required is derived.** Without `default:` the input is required and its value MUST NOT be empty. There is no `required:` key.
- **SY-45.** **At most one constraint:** `in:` or `matches:`, not both.
- **SY-46.** **The `default` MUST satisfy the constraint.** A violation is a plan error.
- **SY-47.** **Defaults are literal.** A reference (`default: { from_env: X }`) is a plan error.
- **SY-48.** **No secret inputs.** `secret:` on an input is a plan error with a fix-it to `env: { X: { from_env: X, secret: true } }`.
- **SY-49.** `description` MUST NOT contain `${`.
- **SY-50.** Inputs bind into the plan scope that encloses the root node; they are used only through the variable forms of §7 and never reach literal fields.

How values are supplied, the value rules and the input error codes are in [variables.md §4](variables.md#4-plan-inputs).

## 6. Scalar grammars

### 6.1 Spec version

**SY-51.** `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`, for example `1.0`. Because every scalar is a string, `blokky: 1.10` is version 1.10, not 1.1.

### 6.2 Names

**SY-52.** Names follow these grammars:

| Name | Grammar | Notes |
|---|---|---|
| Variable (input, capture, `as`, `tempdir.as`, `collect`, `carry`, `index`) | `^[A-Z][A-Z0-9_]*$` | The `BLOKKY_` prefix is reserved. Derived names (`<AS>_INDEX`, `MATRIX_INDEX`) count as declarations. |
| Environment variable (`env:` keys, `from_env`, `env:` subject, `env_pass`) | `^[A-Za-z_][A-Za-z0-9_]*$` | Compared case-insensitively on Windows. Forbidden and reserved names: [variables.md](variables.md). |
| User error code (`fail`, `assert` `code:`) | `^[A-Z][A-Z0-9_]*$` | MUST NOT start with `BK_`. |
| Lock name, service name | `^[a-z0-9][a-z0-9._-]{0,63}$` | |

### 6.3 Booleans

**SY-53.** Exactly `true` or `false`. Unary condition operators (`empty: true`, `exists: true`) accept only `true`.

### 6.4 Integers

**SY-54.** `^(0|[1-9][0-9]*)$`: decimal, no sign, no leading zeros, at most 2 147 483 647. Each field states its allowed range in [reference.md](reference.md) (for example `max` ≥ 1, `concurrency` ≥ 1).

**SY-55.** **Decimals** (`backoff.factor`, `jitter`): `^(0|[1-9][0-9]*)(\.[0-9]+)?$`, no sign, no exponent, invariant culture. Each field states its range.

**SY-96.** **Exit codes** (`ok_exit`, probe `true_exit` and `false_exit`) use the integer grammar with a range of 0 to 4 294 967 295, because Windows exit codes are unsigned 32-bit values. On Unix only 0–255 can occur; larger values are valid (a plan may run on Windows too) and MAY get a warning.

### 6.5 Durations

([ADR 0007](../adr/0007-syntax-details.md))

- **SY-56.** One or more parts `<integer><unit>`, with units `h`, `m`, `s`, `ms`, in that (descending) order, each unit at most once, with no spaces: `500ms`, `10s`, `2m`, `1h30m`, `1m30s500ms`.
- **SY-57.** Integers have no leading zeros and no sign; there are no fractions (`1500ms`, not `1.5s`) and no bare numbers (`timeout: 30` is a plan error with the fix-it `timeout: 30s`).
- **SY-58.** A duration MUST be positive, except in fields that allow `0s` (`every`, `sleep`, `lock.wait`). Zero is written `0s`; zero parts inside a non-zero duration are fine (`1h0m`), but `0ms` or `0m0s` is a plan error.
- **SY-59.** The maximum is 168h (7 days).

### 6.6 Sizes

**SY-60.** `<integer><unit>`, with units `B`, `KiB`, `MiB`, `GiB` (powers of 1024); for example `100MiB`. There are no bare numbers and no decimal (`MB`) units. No plan field takes a size in 1.0; the grammar is used by the conformance testkit.

### 6.7 Regular expressions

**SY-61.** Regex values (`matches`, `not_matches`, input `matches`) use a **portable subset**, close to RE2, so a pattern means the same in every implementation ([ADR 0018](../adr/0018-review-semantics.md)). Implementations validate a pattern against it and translate it for their engine (for blokky-cli: .NET with `RegexOptions.NonBacktracking`). A pattern outside the subset is a plan error. Patterns SHOULD be single-quoted (§8).

| Construct | Meaning |
|---|---|
| a character | itself; `\` escapes any of `.^$*+?()[]{}\|\/` and `-`, and an escape of any other character (`\q`) is outside the subset |
| `.` | any character except LF |
| `[abc]`, `[a-z]`, `[^…]` | a character class; ranges by code point |
| `\d`, `\w`, `\s` (and `\D`, `\W`, `\S`) | ASCII only: `[0-9]`, `[A-Za-z0-9_]`, space, TAB, LF, CR, FF, VT |
| `\t`, `\n`, `\r`, `\xHH`, `\u{H…}` | TAB, LF, CR, a code point |
| `*`, `+`, `?`, `{n}`, `{n,}`, `{n,m}` | greedy repetition; with a trailing `?`, lazy |
| `(…)`, `(?:…)` | a group (captures have no meaning in Blokky) |
| `a\|b` | alternation |
| `^`, `$` | the start and end of the whole value; `$` never matches before a final newline |
| `\b`, `\B` | an ASCII word boundary, or not one |
| `(?i)` at the very start | case-insensitive matching, as for `ignore_case` ([conditions.md](conditions.md), CO-12) |

**SY-62.** Everything else is outside the subset: lookahead and lookbehind, backreferences, atomic groups, possessive quantifiers, named groups, Unicode classes (`\p{…}`), other inline options (`(?m)`, `(?s)`) and anchors such as `\A`, `\z`.

### 6.8 JSON paths

**SY-63.** JSON paths (`json:` in conditions and `for: { items }`, field captures, `fields`) are a jq-like subset ([ADR 0002](../adr/0002-language-core.md)):

- **SY-64.** `.` is the whole value;
- **SY-65.** `.name` selects an object member whose key matches `^[A-Za-z_][A-Za-z0-9_]*$`;
- **SY-66.** `.["any key"]` (double-quoted, JSON string escapes) selects any other member; after the first segment the leading `.` is optional before a bracket (`.a["b-c"]`, `.[0]`);
- **SY-67.** `[N]` selects an array element by non-negative decimal index, without leading zeros (`[0]`, `[10]`, not `[01]`).

**SY-68.** Examples: `.number`, `.head.ref`, `.[0].databaseId`, `.labels[1].name`, `.["weird-key"].x`. Wildcards (`.[]`), negative indices, slices, recursive descent, filters and pipes are plan errors. A path that doesn't resolve at run time is handled where the path is used (a condition error, or a capture failure).

### 6.9 Glob patterns

**SY-69.** `for: { glob }` patterns ([ADR 0018](../adr/0018-review-semantics.md)):

- **SY-70.** `/` separates segments on every OS; a pattern is relative to the node's cwd.
- **SY-71.** `*` matches any run of characters within one segment, `?` one character, `[abc]`, `[a-z]` and `[!…]` one character from a class.
- **SY-72.** `**` as a whole segment matches zero or more directories: `docs/**/*.md` matches `docs/README.md` and `docs/a/b.md`. `**` inside a segment (`a**b`) is a plan error.
- **SY-73.** `\` escapes the next character. There are no braces and no negation patterns: an unescaped `{` or `}` is a plan error, so `{a,b}` doesn't silently match a literal name.
- **SY-74.** Matching is **ordinal and case-sensitive on every OS**, so a plan finds the same items everywhere; on case-insensitive file systems, `*.CS` doesn't match `Program.cs`.
- **SY-75.** The other glob rules (sorting, dotfiles, links, staying under the cwd) are in [reference.md §5.7](reference.md#57-for).

## 7. Values: literals, references and interpolation

### 7.1 Literals

**SY-76.** Most fields are **literal**: the value is taken from the plan text as written. Literal fields never interpolate `${…}` and never accept a reference or an input. A `${` in a literal field other than `script` text is a plan error (§9). Executed text (`exec` strings, `script` text, probe commands) is always literal. In `script` text, `${…}` is the shell's own syntax (`${VAR:-default}`, `${#arr[@]}`, PowerShell `${env:X}`) and is passed to the shell unchanged; implementations SHOULD warn when `${NAME}` in a POSIX script names a plan variable that the node doesn't export, because the author probably expected interpolation.

### 7.2 Whole-value references

**SY-77.** Where a value affects execution and may come from a variable, the field accepts a **reference mapping** instead of a literal:

| Form | Meaning | Allowed in |
|---|---|---|
| `{ var: X }` | The value of plan variable `X`. | `exec` array elements (not argv[0]); `env` values; `cwd`; `path:` subjects; `stdin`; `stdin.file`; `mounts[].host`; `set` and `vars` values. |
| `{ from_env: NAME }` | The value of environment variable `NAME` in the environment the run started with. | `env` values; `set` and `vars` values. |
| `stdin: { var: X }` | The variable's value as the leaf's stdin. | `stdin`. |
| `stdin: { file: P }` | The content of host file `P` (a literal path or `{ var: X }`). | `stdin`. |

- **SY-78.** Any `var` or `from_env` reference MAY carry `secret: true`: `{ from_env: GH_TOKEN, secret: true }`. A literal can't be marked secret.
- **SY-79.** A reference replaces the **whole** value. Executed fields don't concatenate: to build a string such as `--name=${X}` or `page=${N}`, bind it with a `set` template (`set: { ARG: '--name=${X}' }`) and pass `{ var: ARG }`. A path is built by nesting relative `cwd` values (a relative child `cwd` resolves against the parent's cwd).
- **SY-80.** argv[0] of an `exec` array MUST be a literal; a reference there is a plan error.
- **SY-81.** Plan variables reach processes only through four routes: `env:`, `export:`, `exec` array elements and `stdin`. A `{ var: X }` in `cwd`, `stdin.file`, `path:` or `mounts[].host` chooses a location; it doesn't pass the value to the process.

### 7.3 Interpolation in display strings and templates

**SY-82.** `${X}` interpolation exists only in **display strings** (`name`, and the messages of `log`, `fail` and `assert`) and in **templates**, the values of `set` and `vars` ([variables.md §5.6](variables.md#56-set-and-vars)). Templates are how a plan builds a string from variables; every other executed field takes a literal or one whole variable.

- **SY-83.** `${X}` is replaced by the value of plan variable `X`; process environment variables are never interpolated.
- **SY-84.** `$${` produces a literal `${`, in every field, so it is never the "`${` in a literal field" error.
- **SY-85.** A `${X}` whose variable can't be bound at that point is a plan error; one that might be undefined MAY get a warning ([variables.md](variables.md), VA-38); at run time an undefined variable is an error of the node.
- **SY-86.** Non-scalar values (multi-field captures of objects or arrays) render as compact JSON; a `capture_file` variable renders as its path. **Compact JSON**, wherever this spec uses it, is RFC 8259 text with no insignificant whitespace, object members in input order, numbers as written, the short escapes (`\"`, `\\`, `\n`, `\r`, `\t`, `\b`, `\f`) where they exist, `\u00XX` for other control characters, and every other character as itself ([ADR 0022](../adr/0022-wave-b-gaps.md)).
- **SY-87.** Secret values are masked in the rendered text.
- **SY-98.** Rendered text is display-sanitized like error messages: control, bidirectional and zero-width characters from variable values are shown escaped as `\uXXXX` (uppercase hex; `\u{XXXXX}` above U+FFFF), so a captured value can't rewrite what a reviewer sees. This is hygiene, not a control; rendered text and captured values can hold untrusted data and are never instructions.

### 7.4 Per-field table

**SY-88.** Legend: **L** = literal only; **`${}`** = display string with interpolation; **T** = literal, whole-value reference or template (§7.3); **R** = literal or whole-value reference (forms in §7.2); **C** = a condition ([conditions.md](conditions.md)); **N** = a list of nodes. The type column refers to §6. Every field of the language is listed.

#### Root and inputs

| Field | Type | Form |
|---|---|---|
| `blokky` | spec version | L |
| `inputs.<NAME>.default` | string | L |
| `inputs.<NAME>.description` | string | L (never interpolated) |
| `inputs.<NAME>.in` | list of strings | L |
| `inputs.<NAME>.matches` | regex | L |
| `vars.<NAME>` | string, reference or template | T |
| `outputs` | list of variable names | L |
| `defaults.shell` | shell name | L |
| `defaults.leaf_timeout` | duration | L |

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
| `set.<NAME>` | string, reference or template | T |
| `return` | string | `${}` |
| `message` | string | `${}` |
| `code` | user error code | L |
| `concurrency` (`all`, `any`) | integer | L |
| `fail_fast` (`do`, `all`) | boolean | L |

#### Leaf options

| Field | Type | Form |
|---|---|---|
| `stdin` | string, `{ var }` or `{ file }` | R |
| `ok_exit` | list of exit codes (SY-96) | L |
| `stderr` | `merge` | L |
| `encoding` | encoding name | L |
| `keep_descendants` | `true`, `false` or `detach` | L |
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
| `tempdir.remove` | `true`, `false` or `on_success` | L |
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
| `index` | variable name, or `{ as, start }` (`start`: integer) | L |
| `carry` | mapping of variable name → capture name, or → `{ from, initial }` (`initial`: string) | L |
| `collect` (`for`, `while`, `until`) | mapping capture name → list variable name | L |
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
| `container.env_pass` | list of environment variable names | L |
| `services[]` fields | `name` (service name, required), `exec`/`script`, `shell`, `env`, `export`, `cwd` as for leaves and modifiers; `ready` C (required); `ready_timeout` duration L; `on_exit` `fail`/`ignore` L | as listed |

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

#### Conditions

| Field | Type | Form |
|---|---|---|
| `var` | variable name | L |
| `env` (subject) | environment variable name | L |
| `path` | host path | R (`var` only) |
| `command` | program name or path | L |
| `host` | `os`, `arch` | L |
| `result` | `stdout`, `stderr`, `exit`, `error` | L |
| `probe` | probe mapping | see below |
| `probe.exec`, `probe.script`, `probe.shell`, `probe.env`, `probe.export` | as for leaves | as for leaves |
| `probe.timeout` | duration | L |
| `probe.true_exit`, `probe.false_exit` | list of exit codes (SY-96) | L |
| `probe.timeout_result` | boolean | L |
| operator values (`equals`, `in`, `contains`, `matches`, `gt`, …) | string, list of strings, regex or number | L |
| `json` | JSON path | L |
| `ignore_case` | boolean | L |
| `port` | integer | L |
| `output` | `stdout`, `stderr` | L |

## 8. Plain-scalar pitfalls

**SY-89.** YAML plain (unquoted) scalars have traps. Implementations MUST detect the cases below with the stated error or warning.

| Pitfall | Example | Result | Detection |
|---|---|---|---|
| A space then `#` starts a comment | `exec: echo done # tidy` | The command loses `# tidy`. | Warning when a comment follows an `exec`/`script` value on the same line. |
| `[` starts a flow sequence | `script: [ -f x ]` | `script` becomes a list. | Plan error with the fix-it `script: '[ -f x ]'` or a block scalar. |
| `[` in `exec` | `exec: [ -f x ]` | A one-element argv whose program is `-f x`: the flow sequence holds one plain scalar. | Warning that suggests `{ path: x, is_file: true }`, or `exec: ['[', -f, x, ']']`. |
| A leading `"` | `exec: "a" b` | YAML parses a quoted scalar, then fails. | Plan error that explains the quoting. |
| Backslash escapes in double quotes | `matches: "^\d+$"` | `\d` is an invalid YAML escape. | Plan error with the fix-it `matches: '^\d+$'`. |
| Flow mappings with `,` `[` `]` `{` `}` | `{ probe: { exec: a,b } }` | The probe breaks apart. | Plan error that suggests a block mapping. |
| `script:` not a block scalar | `script: npm test && npm run lint` | Works, but fragile. | Warning. |

**SY-90.** Plans and examples SHOULD use: plain scalars only for simple `exec` strings; `script:` text always as a `|` or `|-` block scalar; regexes always single-quoted; block mappings for non-trivial probes.

**SY-97.** Where the language offers several spellings, plans and examples SHOULD use the canonical one:

| Intent | Canonical form | Not |
|---|---|---|
| Run a program with a static argv that needs no quoting | `exec: dotnet build -c Release` (string form) | — |
| Run a program with variables or quoting | `exec: [git, commit, -m, 'fix: typo']`, `{ var: X }` elements | `${X}` in a string |
| Shell text | `script: \|` block scalar with `shell:` | `exec: [bash, -c, …]` |
| Build a string from variables | a `set` template, then `{ var: NAME }` | `exec: [echo, …]` plus `capture` |
| Skip a node | `when:` | `if` without `else` |
| A guard on an optional environment variable | `{ env: NAME, defined: true }` before comparing it | comparing an unset variable |
| Is a program installed? | `{ command: NAME, exists: true }` | a probe running `command -v` |
| Wait or poll until something holds | `until` (with `result:` for output) | `retry: true` with a large `max` |
| Retry a failure | `retry: true` and `max` (attempts, first included) | `until` |

## 9. Targeted errors

**SY-91.** Each of these plan errors names the problem and includes a corrected snippet, and replaces the generic error for the same mistake (SY-3). Codes are assigned in [errors.md](errors.md).

| Mistake | Fix-it |
|---|---|
| A mapping or a single node where a body list is expected (`do: { exec: … }`) | Prefix each node with a dash (`- exec: …`). |
| A string condition (`if: "$X == 1"`) | `if: { var: X, equals: '1' }` |
| GitHub-Actions-style `if:` next to another kind (`exec: …` plus `if: …`) | Use `when:` for a guard. |
| `${X}` in a literal field or an `exec` string | Build the string with a `set` template (`set: { ARG: '--name=${X}' }`) and pass `{ var: ARG }`; for a whole value use `{ var: X }`; for a path, nest a relative `cwd`; in shell text, `"$X"` with `export: [X]`. |
| `retry: 3` | `retry: true` plus `max: 4` (`max` counts attempts, including the first) |
| A bare number for a duration (`timeout: 30`) | `timeout: 30s` |
| A mapping as the value of `exec:`/`script:` (`exec: { cmd: …, timeout: 5m }`) | Move `timeout` (and other options) to the node level. |
| `not: { var: X, equals: a }` | `{ var: X, not_equals: a }` |
| Two kinds in one node | Split into two nodes in a `do:` list. |
| Two repetition modifiers in one node | Nest one node inside the other. |
| A secret literal (`env: { T: { value: abc, secret: true } }`) | Use `{ from_env: T, secret: true }`. |
| Input mistakes: `${{ inputs.X }}`, `{ var: inputs.X }`, `{ input: X }`, a lowercase name, `required:`, `type:`, `secret:`, a list form, `inputs:` below the root | The canonical `inputs:` mapping and `{ var: X }` usage (§5). |

## 10. Versioning

- **SY-92.** A plan names the spec version it targets in `blokky:` (§4.2).
- **SY-93.** Unknown keys are errors (§3.4), so an older implementation fails clearly on a plan that uses newer keys.
- **SY-94.** An implementation that doesn't support a feature yet rejects every plan that uses it with `BK_PLAN_NOT_SUPPORTED` before anything runs ([errors.md](errors.md)).
- **SY-95.** The plan schema (`schema/blokky.schema.json`) is normative for structure; its `$id` is versioned per spec release. Rules the schema can't express are listed in [reference.md](reference.md).
