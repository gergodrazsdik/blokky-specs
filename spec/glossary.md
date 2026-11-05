# Glossary

Status: **draft** (spec 0.1, not yet finalized)

Terms used across the specification, grouped by topic. Each entry gives the short meaning and names the spec file that defines it normatively. Where this glossary and a defining file disagree, the defining file wins. Terms tagged *later* belong to a later milestone: their keywords are reserved in v0.1, and a v0.1 parser rejects them with a "not supported in this version" error.

Code-formatted words (`exec`, `timeout`) are plan keywords; plain words are concepts.

## Plans and documents

- **Plan.** A YAML document that describes what to run: a single root mapping with plan-only keys (`blokky:`, `inputs:`, `outputs:`, `defaults:`) and one root node. See [syntax.md](syntax.md).
- **Plan file.** A plan stored as `*.blokky.yaml` (or `*.blokky.yml`) and run by path, usually together with `--expect-sha256`.
- **Stdin plan.** A plan passed on standard input. The agent convention is a bash heredoc with the quoted delimiter `'BLOKKY_PLAN_EOF'`.
- **Spec version.** The version of this specification a plan targets, written as `MAJOR.MINOR` in the required `blokky:` field (`blokky: 0.1`). Spec patch releases never change the language. See [syntax.md](syntax.md).
- **Plan SHA-256.** The SHA-256 of the exact plan bytes. It appears in `blokky plan`, `leaves`, the validator request and the report, and `--expect-sha256` checks it.
- **Surface rules.** The YAML restrictions every plan obeys: no anchors, aliases, merge keys, explicit tags, multi-document streams, duplicate keys or unknown keys; every scalar is a string. See [syntax.md](syntax.md).
- **Character lint.** One pass over the raw decoded plan text, comments and keys included, before parsing. It allows only TAB, LF and CR as part of CRLF among control characters.
- **Canonical form.** The single preferred spelling of a construct. Examples, the agent guide and fix-it snippets use canonical forms only; other accepted spellings are shorthands.
- **Targeted error.** A parse or validation error that names the problem and includes a corrected YAML snippet (a *fix-it*).
- **Milestone tag.** `v0.1` or `later`, carried by every feature in the reference. Value shapes are fixed for both, so adding a later feature never breaks a plan.
- **Reserved keyword.** A keyword of a later feature (for example `race`, `lock`, `container`, `become`, `services`, `collect`) or one held back for future use (`consent`). Using it is an error in v0.1.

## Nodes

- **Node.** One element of the plan tree. Every node has exactly one **kind** and any number of **modifiers**. See [reference.md](reference.md).
- **Kind.** What a node does: `exec`, `script`, `do`, `all`, `any`, `if`, `sleep`, `log`, `fail`, `assert` (v0.1); `race` (*later*).
- **Leaf.** A node that runs a process: an `exec` or `script` node. Probes and services also run processes but are not leaves.
- **`exec` leaf.** Runs a program directly, without a shell, from an argv array (canonical) or a string split with POSIX shell-like rules and no expansion. See [shells.md](shells.md).
- **`script` leaf.** Writes shell text to a script file in the run dir and runs it with the chosen shell. It compiles to an `exec` of that shell.
- **Group.** A node whose kind runs child nodes: `do` (sequence), `all` (parallel, all must succeed), `any` (first success wins), `race` (*later*, first completion decides).
- **Modifier.** A key that scopes, repeats, limits or labels a node, such as `when`, `timeout`, `cwd`, `env`, `finally`, `retry` or `capture`. Modifiers apply in a fixed order. See [execution-model.md](execution-model.md).
- **Modifier order.** The normative nesting of modifiers, outermost to innermost: `when` → `timeout` → `lock` → `tempdir` → `cwd` → `env` → `container`/`become` → `services` → `finally` → repetition → `attempt_timeout` → kind.
- **Companion field.** A field that belongs to one kind or modifier, such as `then`/`else` for `if`, `shell` for `script`, or `concurrency` and `fail_fast` for `all`.
- **Body field.** A field that holds a list of nodes: `do`, `then`, `else`, `finally`, `all`, `any`, `race`. Body fields take lists only.
- **Path id.** The stable identifier of a node, built from its position in the tree (`/do/2/all/0`). Reports, events, errors and file names use it; `name` values need not be unique.
- **`name`.** A display label for a node, interpolated per attempt or iteration. It never affects execution.
- **Repetition.** One of the mutually exclusive modifiers `retry`, `while`, `until` and `for`. A node has at most one.
- **Attempt.** One execution of a node's body under `retry`.
- **Iteration.** One execution of a node's body under `while`, `until` or `for`.
- **Fan-out.** A `for` with `concurrency` above 1, or an `all`: children or iterations run in parallel, started in declaration order.
- **Concurrency cap.** The free config key `max_concurrency` (default 16). It limits the effective concurrency of each `all`, `any` and `for` node; larger literal values are clamped with a lint warning.
- **Deterministic start order.** Children and iterations always start in declaration (item) order; only completion order and timings vary.
- **`finally`.** Cleanup nodes that run once per node, after success, failure, timeout or cancellation, under their own `finally_timeout`.
- **Static pruning.** Removing a branch before execution because its condition is decidable from the host alone. Only the `host:` subject is pruned statically.

## Variables, inputs and secrets

- **Plan variable.** A named value bound by the plan: an input, a capture, a loop variable (`as`, `<AS>_INDEX`) or a tempdir path (`tempdir.as`). Names match `^[A-Z][A-Z0-9_]*$`; the `BLOKKY_` prefix is reserved. See [variables.md](variables.md).
- **Environment variable.** A process environment entry. Plan variables and environment variables are separate namespaces.
- **Explicit mapping.** The only ways a plan variable reaches a command: `env:` (`env: { RUN: { var: RUN_ID } }`), `export: [NAME]`, or a whole `{ var: X }` element of an `exec` array.
- **Reference.** A whole-value form that stands for a value: `{ var: X }` (a plan variable) or `{ from_env: NAME }` (an environment variable). There is no string concatenation.
- **Literal field.** A field that accepts only a literal value, never a reference or an input: `timeout`, `every`, `max`, `count`, `concurrency`, `each`, `glob`, `shell`, `ok_exit`, `defaults.*`, `tempdir.prefix`, the `inputs.*` keys, and others listed in the per-field table in [syntax.md](syntax.md).
- **Display string.** A string shown to humans and never executed: `name` and the messages of `log`, `fail` and `assert`. Only display strings support `${X}` interpolation.
- **Interpolation.** `${X}` in a display string, replaced by the value of plan variable `X`. Executed text never interpolates.
- **Plan input.** A string parameter declared under the root `inputs:` key, constrained by at most one of `in:` or `matches:`, required unless it has a `default:`. Values come only from `--input NAME=VALUE` or the MCP `inputs` object. Inputs are always defined and never secret. See [variables.md](variables.md).
- **Plan scope.** The scope that holds the inputs and encloses the root node, bound before anything runs.
- **Scope.** The region of the plan where a variable is visible. Captures are visible to later siblings and their descendants; loop-body captures stay inside the loop; captures under `finally` are finally-local.
- **Shadowing.** Binding a name that an enclosing scope already binds. It is a static error.
- **Capture.** The `capture` modifier on a leaf: binds the leaf's stdout (with trailing CR/LF removed) to a variable, or several JSON fields to several variables. Over `max_capture_bytes` (default 1 MiB) it is an error, never a truncation.
- **`capture_file`.** Writes a leaf's stdout to a runtime-owned file in the run dir and binds the file's path. For large outputs.
- **JSON path.** The minimal jq-like path syntax used by `json:` in conditions and by multi-field captures: `.`, `.name`, `.["any key"]`, `[N]`.
- **Trimming.** Removing every trailing `\n` and `\r` from process output when it becomes a value (captures, `result: stdout|stderr`, probe stdout). Nothing else is trimmed.
- **`outputs`.** The root key that names the variables a plan publishes in its report.
- **Secret.** A value marked as sensitive: from `{ from_env: NAME, secret: true }`, a `var` reference to a secret, or a capture with `secret: true`. Secrets come only by reference, never as inputs or literals.
- **Masking.** Replacing secret values in runtime output (stderr, tails, logs, events, display strings, the validator request). Masking is hygiene, not secrecy.
- **`collect`** (*later*). Gathers one captured value per `for` iteration into a list variable, ordered by item index.

## Conditions

- **Condition.** The construct used by `if`, `when`, `assert`, `while`, `until`, `retry` and (*later*) `ready`: one subject key plus one operator key, or a composite, or a bare probe. See [conditions.md](conditions.md).
- **Subject.** What a condition looks at: `var`, `env`, `path`, `host`, `result`, `probe` (v0.1); `port`, `output` (*later*, services only).
- **Operator.** How the subject is tested: `equals`, `in`, `contains`, `matches`, `empty`, `defined`, `exists`, `is_file`, `is_dir`, `open`, `gt`/`ge`/`lt`/`le`, and their negations where defined.
- **Composite.** `all`, `any` or `not` over nested conditions.
- **Probe.** A condition subject that runs a short `exec` or `script` and is true or false by its exit code. The only subject that spawns a process. Default `probe_timeout` 30s, stdout limit 64 KiB.
- **Condition error.** A condition that can be neither true nor false: an undefined variable, a path that doesn't resolve, a value that isn't a number for `gt`. The owning node fails with the built-in condition-error code; a condition error is never "false".

## Execution

- **Run.** One execution of a plan by `blokky run`, from start to the final report.
- **Run id.** The unique, sortable identifier of a run. It is in the report and exported to leaves as `BLOKKY_RUN_ID`.
- **Status.** The outcome of a node: `succeeded`, `failed`, `skipped`, `timed_out` or `cancelled`. A failed node whose failure doesn't fail its parent (`ignore_errors`) also carries `ignored: true`.
- **`timeout`.** A node's total wall-clock limit, covering everything inside it. A node is `timed_out` only if its own `timeout` or `attempt_timeout` fired.
- **`attempt_timeout`.** The limit for a single attempt or iteration. Valid only with a repetition modifier.
- **`leaf_timeout`.** A default limit for leaves and probes without their own `timeout`. There is none unless `defaults.leaf_timeout` or config sets one.
- **Grace period.** The time between the graceful signal (TERM, or CTRL_BREAK on Windows) and the forced kill. Default 5s. It comes after a `timeout`, not inside it.
- **Drain timeout.** How long a leaf's pipes are read after its direct child exits. Default 2s.
- **Run budget.** The maximum duration of a whole run, aligned with agent-harness tool timeouts. Default 1m50s when no explicit budget is set; `--max-duration`, `BLOKKY_MAX_DURATION` or config set an explicit one, and the smallest explicit value wins.
- **Cleanup reserve.** The final part of the run budget kept for cancellation, `finally` and the report (`cleanup_reserve`, default 30s). It is also the single cleanup deadline in cancel and shutdown mode.
- **Cancellation.** Stopping nodes early because a sibling failed (`fail_fast`), an `any` or `race` was decided, a limit fired, or the run is shutting down. Cancelled processes get the graceful signal, then the forced kill.
- **Shutdown mode.** What Blokky does on SIGINT, SIGTERM, SIGHUP or a Windows console control event: cancel everything, run `finally`, write a partial report, exit with 128+N.
- **Process tree kill.** Killing a leaf with everything it started: its own session (Unix) or Job Object (Windows).
- **Descendants.** Processes a leaf started. By default the leaf's remaining session or job is killed when the leaf completes; `keep_descendants: true` opts out. Every descendant dies no later than run end.
- **Lifeline.** The mechanism that kills all leaves when Blokky itself dies, even by SIGKILL. Its implementation is decided by spike #1.
- **Trampoline.** A `blokky __exec` helper process that sets up a leaf (and, for `become`, receives argv, env and script text over a pipe). Whether it launches every leaf is decided by spike #1.
- **Invocation.** The exact command line Blokky runs for a leaf, including the shell flags and prologue for `script` leaves. A single invocation builder renders what `leaves` shows and what is executed.
- **Shell.** A program that runs `script` leaves: `bash`, `sh`, `pwsh`, `powershell` (v0.1); `zsh`, `fish` (*later*). `cmd` is not supported.
- **Prologue.** Setup applied to every script of a shell, shown in `leaves`: `-o pipefail` for bash, `$ErrorActionPreference = 'Stop'` for PowerShell, none for `sh`.

## Runs and artefacts

- **State dir.** The per-user directory that holds run dirs, the run registry and locks. Never inside a repo.
- **Run dir.** A run's directory in the state dir: `report.json`, `events.jsonl`, leaf logs, script files and capture files.
- **Artefact.** Anything a run leaves behind: the report, the event log, logs, capture files, script files, tempdirs and (*later*) stopped containers. Artefacts are kept until `clean` or `gc`.
- **Registry.** The record of each run's artefacts in the state dir. `clean` and `gc` delete only what it lists.
- **`tempdir`.** A runtime-owned temporary directory created for a node (0700, unpredictable name). It always becomes the node's cwd.
- **In progress.** A run whose advisory lock on its registry entry is still held. `clean` and `gc` never touch runs in progress.

## Output

- **Report.** The JSON document describing a run: run-level fields and one entry per node in plan order. Printed on stdout (size-capped) and stored in full as `report.json`. See [blokky-cli output-contract.md](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/output-contract.md).
- **Pre-run envelope.** The JSON printed on stdout when a run fails before execution (parse, character-lint, sha-mismatch, config or input errors). It has no run id, and every error is listed at once.
- **Event log.** `events.jsonl`, the append-only, sequence-numbered log of a run's events.
- **Tail.** The last part of a leaf's stdout or stderr kept for the report: the last 50 lines, at most 4 KiB per stream.
- **Truncation.** Deterministic shortening of the stdout report to its byte budget (32 KiB): succeeded subtrees collapse first, then loop iterations aggregate, then tails shrink. The full report stays in `report.json`.
- **`killed_by`.** Why a leaf was killed: `timeout`, `attempt_timeout`, `cancel`, `shutdown` or `budget`.
- **Error code.** The machine-readable code of an error. Built-in codes start with `BK_` (see [errors.md](errors.md)); user codes (from `fail` and `assert`) match `^[A-Z][A-Z0-9_]*$` and must not start with `BK_`.
- **`schema_version`.** The version field of each JSON contract (report, events, `leaves`, validator protocol). Consumers ignore unknown fields.

## Validation and approval

- **`leaves`.** The document (and the `blokky leaves` command) that lists everything a plan will execute, as units, with plan-dependent effects and flags. It spawns no process. See [blokky-cli leaves-and-validation.md](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/leaves-and-validation.md).
- **Unit.** One entry in `leaves`: an `exec`, `script`, `probe`, `service` (*later*) or `derived` command (*later*, for example a container engine call).
- **Rendered form.** A unit written as the equivalent one-line command in the unit's own shell syntax, with env assignments as a prefix, so humans and rule matchers can read it like the equivalent bash call.
- **Dynamic marker.** `<dynamic>` in a unit where a value is only known at run time (a capture). Missing inputs show as `<input:NAME>` instead.
- **Effect.** A plan-dependent read or write that isn't a process: `path:` subjects, glob roots, the tempdir prefix, `capture_file`, `stdin: { file }` sources, readiness targets.
- **`dynamic_exec`.** A flag on a unit that runs a variable as code (`sh -c` with a variable, `eval`, `source`, `iex`, a variable in command position).
- **`exec_env_risk`.** A flag on a unit whose environment sets an execution-influencing variable (`LD_*`, `NODE_OPTIONS`, `GIT_SSH_COMMAND`, …).
- **Validator.** An optional user-configured executable that receives the `leaves` document as JSON and answers `allow`, `deny` or `ask`, optionally per unit. Any failure counts as `ask`.
- **Hook.** `blokky hook check <runner>`: integrates Blokky with an agent runner's permission system. It never passes a call through: it answers `allow`, `deny` or `ask`.
- **Runner.** The agent harness that executes tool calls and owns the permission system (Claude Code in v0.1).
- **Runner-rules mode.** `hook check --rules`: matches each `exec` unit against the runner's own Bash allow and deny rules, as if it were a separate Bash call.
- **Approval record.** A single-use record the hook stores when it answers `allow` or `ask`, holding the plan bytes, inputs, cwd and resolved locations. `blokky run --approval <id>` runs exactly that.
- **Invocation digest.** The hash that binds an approval to `{ plan_sha256, spec_version, inputs, cwd }`.
- **`inputs_sha256`.** The SHA-256 of the canonical JSON (RFC 8785) of a run's effective inputs.

## Configuration and lint

- **Config file.** A JSONC file at user, repo (`.blokky/config.json`) or repo-local (`.blokky/config.local.json`) level. Defined in blokky-cli.
- **User-only key.** A config key that only the user-level file may set: executable paths, locations, enabling switches, approval and rules-mode settings. Anywhere else it is a config error.
- **Free key.** Any other config key: defaults, timers, caps, lint severities, `strict`.
- **Lint rule.** A named check (kebab-case ID) with a severity: `off`, `info`, `warning` or `error`. Only `error` blocks a run.
- **Strict mode.** `strict: true`: a preset that raises the script-hygiene lint rules to `error`. Strict mode is hygiene, not a control.
- **Hygiene vs control.** Hygiene (lint, strict mode, masking, display sanitization) makes plans cleaner and more reviewable. Controls (the runner's permissions, the hook, the validator) decide what may run. The spec never presents hygiene as a control.

## Containers, privilege and locks (*later*)

- **`container`.** A modifier that runs a node's leaves in an ephemeral container Blokky starts for the node and stops afterwards. By default the cwd is mounted read-write at the same path. See [containers-and-privilege.md](containers-and-privilege.md).
- **Mount.** A host path made visible in a container: `{ host, path, read_only }`.
- **`become`.** A modifier that runs a node's leaves as another user, through `sudo -n` or `doas -n`, or by dropping privileges when Blokky runs as root.
- **`invoker`.** A special `become` value: the user who invoked sudo or doas (from `SUDO_UID` or the doas equivalent), or the current user when not elevated.
- **`lock`.** A named advisory lock a node holds while it runs. Locks don't nest.
- **`services`.** Background processes started before a node, checked with a `ready:` condition, and stopped (whole tree) after it.

## Project

- **Conformance suite.** The implementation-independent test cases in `conformance/`, run by blokky-cli CI against the release binary at a pinned blokky-specs version.
- **Testkit.** Fake executables with scripted behaviour used by conformance cases. The interface is specified in `conformance/testkit-interface.md`; the implementation lives in blokky-cli.
- **Spike.** A time-boxed experiment on an unmerged `spikes/*` branch in blokky-cli that verifies runtime behaviour the spec depends on. Items marked *provisional — verify in spike* are resolved by spikes before the spec is finalized.
