# Glossary

Status: **draft** (`1.0.0-draft`, not yet finalized)

Terms used across the specification, grouped by topic. Each entry gives the short meaning and names the spec file that defines it normatively. Where this glossary and a defining file disagree, the defining file wins. Every feature belongs to the language 1.0; implementations may support them step by step.

Code-formatted words (`exec`, `timeout`) are plan keywords; plain words are concepts.

## Plans and documents

- **Plan.** A YAML document that describes what to run: a single root mapping with plan-only keys (`blokky:`, `inputs:`, `outputs:`, `defaults:`) and one root node. See [syntax.md](syntax.md).
- **Plan file.** A plan stored as `*.blokky.yaml` (or `*.blokky.yml`) and run by path.
- **Stdin plan.** A plan passed on standard input, typically from a bash heredoc with a quoted delimiter.
- **Spec version.** The version of this specification a plan targets, written as `MAJOR.MINOR` in the required `blokky:` field (`blokky: 1.0`). Spec patch releases never change the language. See [syntax.md](syntax.md).
- **Plan SHA-256.** The SHA-256 of the exact plan bytes. It is part of the run result, and implementations can use it to check that the plan reviewed is the plan run.
- **Surface rules.** The YAML restrictions every plan obeys: no anchors, aliases, merge keys, explicit tags, multi-document streams, duplicate keys or unknown keys; every scalar is a string. See [syntax.md](syntax.md).
- **Character lint.** One pass over the raw decoded plan text, comments and keys included, before parsing. It allows only TAB, LF and CR as part of CRLF among control characters.
- **Canonical form.** The single preferred spelling of a construct. Examples, the agent guide and fix-it snippets use canonical forms only; other accepted spellings are shorthands.
- **Targeted error.** A parse or validation error that names the problem and includes a corrected YAML snippet (a *fix-it*).
- **Not supported.** A feature an implementation doesn't support yet. Plans that use it are rejected before anything runs (`BK_PLAN_NOT_SUPPORTED`); the language itself is the same for every implementation.

## Nodes

- **Node.** One element of the plan tree. Every node has exactly one **kind** and any number of **modifiers**. See [reference.md](reference.md).
- **Kind.** What a node does: `exec`, `script`, `do`, `all`, `any`, `race`, `if`, `sleep`, `log`, `fail`, `assert`, `set`, `return`.
- **Leaf.** A node that runs a process: an `exec` or `script` node. Probes and services also run processes but are not leaves.
- **`exec` leaf.** Runs a program directly, without a shell, from an argv array (canonical) or a string split with POSIX shell-like rules and no expansion. See [shells.md](shells.md).
- **`script` leaf.** Writes shell text to a script file owned by the run and runs it with the chosen shell. It compiles to an `exec` of that shell.
- **Group.** A node whose kind runs child nodes: `do` (sequence), `all` (parallel, all must succeed), `any` (first success wins), `race` (first completion decides).
- **Modifier.** A key that scopes, repeats, limits or labels a node, such as `when`, `timeout`, `cwd`, `env`, `finally`, `retry` or `capture`. Modifiers apply in a fixed order. See [execution-model.md](execution-model.md).
- **Modifier order.** The normative nesting of modifiers, outermost to innermost: `when` → `timeout` → `lock` → `tempdir` → `cwd` → `env` → `container` → `services` → `finally` → repetition → `attempt_timeout` → kind.
- **Companion field.** A field that belongs to one kind or modifier, such as `then`/`else` for `if`, `shell` for `script`, or `concurrency` and `fail_fast` for `all`.
- **Body field.** A field that holds a list of nodes: `do`, `then`, `else`, `finally`, `all`, `any`, `race`. Body fields take lists only.
- **Path id.** The stable identifier of a node, built from its position in the tree: the root is `/`, and a node in a body field adds `/<field>/<index>` (`/do/2/all/0`, `/then/1`, `/finally/0`). See [reference.md §1](reference.md#1-node-anatomy). Run results and errors use it; `name` values need not be unique.
- **`name`.** A display label for a node, interpolated per attempt or iteration. It never affects execution.
- **Repetition.** One of the mutually exclusive modifiers `retry`, `while`, `until` and `for`. A node has at most one.
- **Attempt.** One execution of a node's body under `retry`.
- **Iteration.** One execution of a node's body under `while`, `until` or `for`.
- **Fan-out.** A `for` with `concurrency` above 1, or an `all`: children or iterations run in parallel, started in declaration order.
- **Concurrency cap.** An implementation's upper limit on a node's effective concurrency. It reduces parallelism only, never start order or results ([execution-model.md](execution-model.md), EM-11).
- **Deterministic start order.** Children and iterations always start in declaration (item) order; only completion order and timings vary.
- **`finally`.** Cleanup nodes that run once per node, after success, failure, timeout or cancellation, under their own `finally_timeout`.
- **Static pruning.** Removing a branch before execution because its condition is decidable from the host alone. Only the `host:` subject is pruned statically.

## Variables, inputs and secrets

- **Plan variable.** A named value bound by the plan: an input, a plan constant (`vars`), a `set` variable, a capture, a loop variable (`as`, `<AS>_INDEX`, `fields`, `index`, `carry`) or a tempdir path (`tempdir.as`). Every variable is bound once. Names match `^[A-Z][A-Z0-9_]*$`; the `BLOKKY_` prefix is reserved. See [variables.md](variables.md).
- **Environment variable.** A process environment entry. Plan variables and environment variables are separate namespaces.
- **Explicit mapping.** The only ways a plan variable reaches a command: `env:` (`env: { RUN: { var: RUN_ID } }`), `export: [NAME]`, or a whole `{ var: X }` element of an `exec` array.
- **Reference.** A whole-value form that stands for a value: `{ var: X }` (a plan variable) or `{ from_env: NAME }` (an environment variable). There is no string concatenation.
- **Literal field.** A field that accepts only a literal value, never a reference or an input: `timeout`, `every`, `max`, `count`, `concurrency`, `each`, `glob`, `shell`, `ok_exit`, `defaults.*`, `tempdir.prefix`, the `inputs.*` keys, and others listed in the per-field table in [syntax.md](syntax.md).
- **Display string.** A string shown to humans and never executed: `name` and the messages of `log`, `fail` and `assert`. Display strings support `${X}` interpolation.
- **Template.** A `set` or `vars` value containing `${X}` placeholders: the one way a plan builds a string from variables. Templates only join strings; there are no functions.
- **`set`.** A node kind that binds variables from literals, references or templates, scoped like a capture.
- **`vars`.** The root key for plan constants: variables bound before anything runs, from literals, inputs, earlier `vars` and `from_env`; the caller can't override them.
- **Interpolation.** `${X}` in a display string or template, replaced by the value of plan variable `X`. Executed text (`exec` strings, `script` text, probes) never interpolates.
- **Plan input.** A string parameter declared under the root `inputs:` key, constrained by at most one of `in:` or `matches:`, required unless it has a `default:`. Values come only from `--input NAME=VALUE` or the MCP `inputs` object. Inputs are always defined and never secret. See [variables.md](variables.md).
- **Plan scope.** The scope that holds the inputs and encloses the root node, bound before anything runs.
- **Scope.** The region of the plan where a variable is visible. Captures are visible to later siblings and their descendants; loop-body captures stay inside the loop; captures under `finally` are finally-local.
- **Shadowing.** Binding a name that an enclosing scope already binds. It is a static error.
- **Capture.** The `capture` modifier on a leaf: binds the leaf's stdout (with trailing CR/LF removed) to a variable, or several JSON fields to several variables. Over `max_capture_bytes` (default 1 MiB) it is an error, never a truncation.
- **`capture_file`.** Writes a leaf's stdout to a file owned by the run and binds the file's path. For large outputs.
- **JSON path.** The minimal jq-like path syntax used by `json:` in conditions and by multi-field captures: `.`, `.name`, `.["any key"]`, `[N]`.
- **Trimming.** Removing every trailing `\n` and `\r` from process output when it becomes a value (captures, `result: stdout|stderr`, probe stdout). Nothing else is trimmed.
- **`outputs`.** The root key that names the variables a plan publishes in its run result.
- **Secret.** A value marked as sensitive: from `{ from_env: NAME, secret: true }`, a `var` reference to a secret, or a capture with `secret: true`. Secrets come only by reference, never as inputs or literals.
- **Masking.** Replacing secret values with `***` in everything an implementation shows, keeps or passes on about a run. Masking is hygiene, not secrecy.
- **`collect`**. Gathers one captured value per iteration of a `for`, `while` or `until` into a list variable, in iteration order.
- **`carry`.** A `while`/`until` field that passes a capture from one iteration to the next: the carried variable is bound once per iteration, to `''` (or `initial`) first and then to the previous iteration's value. It is how a loop follows a cursor.
- **`index`.** A `retry`/`while`/`until` field that binds the attempt or iteration number to a named variable.
- **`return`.** A node kind that ends the nearest enclosing sequence successfully; the remaining nodes are `skipped` (`returned`). See [reference.md §2.13](reference.md#213-return).

## Conditions

- **Condition.** The construct used by `if`, `when`, `assert`, `while`, `until`, `retry` and `ready`: one subject key plus one operator key, or a composite, or a bare probe. See [conditions.md](conditions.md).
- **Subject.** What a condition looks at: `var`, `env`, `path`, `command`, `host`, `result`, `probe`; `port`, `output` (services only).
- **Operator.** How the subject is tested: `equals`, `in`, `contains`, `matches`, `empty`, `defined`, `exists`, `is_file`, `is_dir`, `open`, `gt`/`ge`/`lt`/`le`, and their negations where defined.
- **Composite.** `all`, `any` or `not` over nested conditions.
- **Probe.** A condition subject that runs a short `exec` or `script` and is true or false by its exit code. The only subject that spawns a process. Default `probe_timeout` 30s, stdout limit 64 KiB.
- **Condition error.** A condition that can be neither true nor false: an undefined variable, a path that doesn't resolve, a value that isn't a number for `gt`. The owning node fails with the built-in condition-error code; a condition error is never "false".

## Execution

- **Run.** One execution of a plan, from validation to the run result.
- **Run id.** The unique, sortable identifier of a run. It is in the run result and exported to leaves as `BLOKKY_RUN_ID`.
- **Status.** The outcome of a node: `succeeded`, `failed`, `skipped`, `timed_out` or `cancelled`. A failed node whose failure doesn't fail its parent (`ignore_errors`) also carries `ignored: true`.
- **`timeout`.** A node's total wall-clock limit, covering everything inside it. A node is `timed_out` only if its own `timeout` or `attempt_timeout` fired.
- **`attempt_timeout`.** The limit for a single attempt or iteration. Valid only with a repetition modifier.
- **`leaf_timeout`.** A default limit for leaves and probes without their own `timeout`. There is none unless `defaults.leaf_timeout` sets one.
- **Grace period.** The time between the graceful signal (TERM, or CTRL_BREAK on Windows) and the forced kill. Default 5s. It comes after a `timeout`, not inside it.
- **Cancellation.** Stopping nodes early because a sibling failed (`fail_fast`), an `any` or `race` was decided, a limit fired, or the run is stopped from outside. Cancelled processes get the graceful signal, then the forced kill.
- **External stop.** The implementation stopping a whole run from outside the plan (for example a run budget or an interrupt): running nodes are cancelled, `finally` runs as time allows, and the run's status is `stopped` ([execution-model.md §7](execution-model.md#7-external-stops)).
- **Process tree kill.** Stopping a leaf together with everything it started.
- **Descendants.** Processes a leaf started. By default the leaf's remaining process tree is stopped when the leaf completes; `keep_descendants: true` keeps it until the run ends, and `detach` leaves it running after the run (a daemon).
- **Invocation.** The exact command line run for a leaf, including the shell flags and prologue for `script` leaves. It is determined statically ([shells.md](shells.md)).
- **Shell.** A program that runs `script` leaves: `bash`, `sh`, `pwsh`, `powershell`, `zsh`. `cmd` and `fish` are not supported.
- **Prologue.** Setup applied to every script of a shell, part of the invocation: `-o pipefail` for bash, `$ErrorActionPreference = 'Stop'` for PowerShell, none for `sh`.

## Runs and results

- **Run result.** The abstract outcome of a run: its status, inputs, outputs, errors and one result per node in plan order. Conformance cases assert on it; implementations serialize it (for blokky-cli: the JSON run report). See [results.md](results.md).
- **Run-owned files.** Files a run creates for itself: script files, capture files and tempdirs. They are readable only by the run's user, outlive the run, and are removed by the implementation when asked (for blokky-cli: `blokky clean`).
- **`tempdir`.** A run-owned temporary directory created for a node (0700, unpredictable name). It always becomes the node's cwd; `remove` deletes it at node end.
- **`killed_by`.** Why a run stopped a leaf: `timeout`, `attempt_timeout`, `cancel`, or the cause of an external stop.
- **Error code.** The machine-readable code of an error. Built-in codes start with `BK_` (see [errors.md](errors.md)); user codes (from `fail` and `assert`) match `^[A-Z][A-Z0-9_]*$` and must not start with `BK_`.

## Review and controls

- **Static view.** Anything an implementation shows about a plan before running it (for example the processes it can start), derived from the plan and its inputs alone. Everything a plan can execute is determinable this way, except values only known at run time.
- **Warning.** A finding about something legal but likely wrong. Warnings never block a run by themselves.
- **Runner.** The agent harness that executes tool calls and owns the permission system (for example Claude Code).
- **Hygiene vs control.** Hygiene (warnings, masking, display sanitization) makes plans cleaner and more reviewable. Controls (the runner's permission system and the implementation's approval mechanisms) decide what may run. The spec never presents hygiene as a control.
- **Implementation terms.** The report, event log, `leaves` document, hook, validator, approval records, run budget, configuration and lint rules belong to the implementation, not the language; for blokky-cli see [`docs/contracts/`](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/) and its configuration docs.

## Containers, services and locks

- **`container`.** A modifier that runs a node's leaves in an ephemeral container started for the node and stopped afterwards. By default the cwd is mounted read-write at the same path. See [containers.md](containers.md).
- **Mount.** A host path made visible in a container: `{ host, path, read_only }`.
- **`lock`.** A named, exclusive lock a node holds while it runs, shared by all runs of the same user on the machine. Locks don't nest. See [reference.md §4.4](reference.md#44-lock).
- **`services`.** Background processes started before a node (one at a time, in list order, each ready before the next), each checked with a required `ready:` condition, and stopped (whole tree, reverse order) after it. See [reference.md §4.9](reference.md#49-services).
- **`fields`.** A `for: { items }` option that binds variables from each JSON item per iteration.

## Project

- **Conformance suite.** The implementation-independent test cases in `conformance/`, run by blokky-cli CI against the release binary at a pinned blokky-specs version.
- **Testkit.** Fake executables with scripted behaviour used by conformance cases. The interface is specified in `conformance/testkit-interface.md`; the implementation lives in blokky-cli.
- **Spike.** A time-boxed experiment on an unmerged `spikes/*` branch in blokky-cli that verifies runtime behaviour the spec depends on. Items marked *provisional — verify in spike* are resolved by spikes before the spec is finalized.
