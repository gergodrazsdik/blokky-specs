# 0001: Language baseline

- Status: accepted
- Date: 2026-11-04
- Questions: Q14, Q-p (answered in the brief; recorded here)

## Context and problem statement

The [specification-phase brief](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/design/brief.md) (§2, §3) sets the current direction for the Blokky language before any spec text is written. Later ADRs answer the brief's open questions (§4) batch by batch, and they need a recorded starting point to refine or supersede.

This ADR records the **language-level** baseline. Implementation, CLI, configuration, distribution and process decisions are in [blokky-cli ADR 0001](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/adr/0001-baseline.md).

Baseline decisions are the current direction, not frozen (brief §1.5): everything can change until v1.0.0, and changing a baseline decision needs the maintainer's approval and a superseding ADR.

## Considered options

1. One grouped baseline ADR per repo that summarizes the brief's baseline and links to it.
2. One ADR per baseline decision.
3. No ADR; treat the brief as the record.

## Decision outcome

Chosen option: "one grouped baseline ADR per repo", because the brief asks for grouped ADRs (§8 step 2), per-decision files would add dozens of near-empty records, and the brief is a phase document that later ADRs can't supersede piece by piece.

The language baseline:

### Scope and posture

- Blokky is a **small, declarative YAML block language** that wraps shell commands in structured-programming blocks. It is not a scripting language: a feature that needs a general expression language probably doesn't belong (brief §1.1).
- Its primary users are coding agents; its secondary users are the humans who review what agents run.
- **Security baseline: the same as plain bash.** Blokky must never be less safe than the equivalent shell call, should be more reviewable, and must not grant capabilities, bypass the runner's permission system or hide what will run. Blokky is not a sandbox and does not decide what is allowed (brief §1.2).
- Hygiene (strict lint, secret masking, display sanitization, excluding `cmd`) is not a control; the spec must not present it as one.

### Versioning and spec structure

- The language spec is versioned separately from the implementation, with its own semver. A plan's `blokky:` field names the spec version it targets (scheme and whether it is required: Q13).
- The draft spec describes **all** planned features, each tagged `v0.1` or `later`. Value shapes are fixed now, even for later features, so no scalar → mapping breaking change is needed later. Later keywords are reserved and rejected with a "not supported in this version" error (brief §1.6).
- The JSON Schema (`schema/blokky.schema.json`) is normative for structure; `spec/reference.md` is normative for semantics and lists every rule the schema can't express.

### Plan format and surface

- **YAML with strict surface rules** (brief §3.0): anchors, aliases, merge keys, explicit tags, multi-document streams, duplicate keys, unknown keys (with did-you-mean and a synonym table), empty required values and empty lists are rejected.
- **Every scalar is a string;** there is no YAML 1.1 implicit typing. Booleans are exactly `true`/`false`.
- A character lint over the raw text (comments and keys included) allows only TAB, LF and CR as part of CRLF; plan size and nesting depth are capped before the AST is built.
- Targeted errors carry a corrected YAML snippet.
- The root is a single mapping. Plan-only root keys: `blokky:`, `inputs:`, `outputs:`, `defaults:` (closed set: `shell`, `leaf_timeout`, later `become`).
- Plan files use `*.blokky.yaml` (also `*.blokky.yml`). The agent convention is stdin via a heredoc with the quoted delimiter `'BLOKKY_PLAN_EOF'`; a file path is also supported.

### Nodes

- A plan is a tree of **nodes**. Each node has **exactly one kind**, plus optional **modifiers** that scope, repeat, limit or label it; companion fields belong to their kind; body fields (`do`, `then`, `else`, `finally`, `all`, `any`, `race`) take lists only (brief §3.1).
- Kinds: `exec`, `script`, `do`, `all`, `any`, `if`, `sleep`, `log`, `fail`, `assert` (v0.1); `race` (later).
- Modifiers: `name`, `when`, `timeout`, `tempdir`, `cwd`, `env`, `export`, `finally`, `ignore_errors`, `retry`, `while`, `until`, `for` (`each`, `count`, `glob`), `attempt_timeout`, `capture`/`capture_file` (v0.1); `lock`, `container`, `become`, `services`, `for` over `items`/`lines`/`matrix`, `collect` (later); `consent` is reserved.
- At most one repetition modifier per node; `while`/`until` must be bounded by `max` and/or `timeout`.
- **Deterministic start order:** children and iterations start in declaration order; only completion order and timings vary. The report lists nodes in plan order.

### Leaves and shells

- Two leaf kinds (brief §3.5): **`exec`** runs a program without a shell (an argv array, or a string split with POSIX shlex rules and no expansion); **`script`** writes shell text to a file and runs it with the chosen shell. `exec` is the primitive: a `script` leaf compiles to an `exec` of the shell with the script file.
- Shells: `bash`, `sh`, `pwsh`, `powershell` (v0.1); `zsh`, `fish` (later).
- **`cmd` is not supported:** it textually expands `%X%` before parsing, so passing values via the environment would degrade to textual substitution.

### Variables, inputs and secrets

- **Plan variables and environment variables are separate namespaces.** Plan variables reach commands only through explicit mapping: `env:` (`env: { RUN: { var: RUN_ID } }`), `export: [NAME, …]`, or whole `{ var: X }` elements of `exec` arrays (Q-p).
- **Executed text never interpolates.** `${X}` interpolation exists only in display strings (`name`, `log`/`fail`/`assert` messages) and resolves Blokky variables only. Every field that affects execution takes either a literal or a whole-value reference (`{ var: X }`, `{ from_env: NAME }`); there is no string concatenation.
- Variable names match `^[A-Z][A-Z0-9_]*$`; the `BLOKKY_` prefix is reserved. Shadowing is an error.
- **Plan inputs** (brief §3.3) are root-only, strings only, constrained by at most one of `in:`/`matches:`, required unless they have a `default:`. Values come only from the CLI (`--input NAME=VALUE`) or the MCP `inputs` object. Inputs never reach literal fields, and there are no secret inputs.
- **Secrets come only by reference** (`from_env`, `var` or captures marked `secret: true`). Masking is hygiene, not secrecy.

### Conditions

- One reusable condition construct for `if`, `when`, `assert`, `while`, `until`, `retry` and (later) `ready`: one subject key plus one operator key, composites `all`/`any`/`not`, and the bare probe as the only operator-less form (brief §3.1). `matches` uses .NET `RegexOptions.NonBacktracking` (exact semantics: Q3).
- All subjects are evaluated by Blokky without spawning a process, except `probe`. `host:` is the only statically pruned subject.

### Execution semantics fixed at language level

- Leaves never read interactive input: stdin is `/dev/null` unless the plan supplies `stdin:`, and leaves have no controlling terminal. Blokky never prompts for, accepts or forwards passwords (brief §3.7).
- Timeouts and cancellation kill the leaf's **whole process tree**, graceful then forced.
- **Q14:** at leaf completion the leaf's remaining session/job is killed by default; `keep_descendants: true` opts out and is visible in `leaves`. Every descendant dies no later than run end.
- Every run has a unique, sortable run id, exported to leaves as `BLOKKY_RUN_ID`.

### Contracts

- The run report, event log, `leaves` output and validator protocol are language-level contracts specified in this repo, each with its own `schema_version`; consumers ignore unknown fields.
- stdout carries the final JSON report and nothing else.
- Built-in error codes use the reserved `BK_` prefix; user codes match `^[A-Z][A-Z0-9_]*$` and must not start with `BK_`.
- Durations use the grammar `500ms`, `10s`, `2m`, `1h30m`; there are no bare numbers.

### Consequences

- Good: the draft spec PRs (tracker T-0014 to T-0025) start from a recorded, linkable baseline.
- Good: each open-question ADR states which baseline item it refines.
- Neutral: details stay in the brief and, once written, in the spec; this ADR only summarizes the direction.
- Bad: two places describe the baseline until the spec exists. Once the spec is written, it is authoritative for the details and this ADR records only the decisions.

## More information

- Brief: §1 (principles, posture), §2 (baseline decisions), §3 (language model).
- Open questions that refine this baseline: tracker [Open questions](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/plan/TRACKER.md#open-questions), batches T-0008 to T-0013.
- Companion: [blokky-cli ADR 0001](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/adr/0001-baseline.md) (implementation, CLI, configuration, distribution, process).
