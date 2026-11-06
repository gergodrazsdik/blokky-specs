# Prior art

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is **informative**. It describes tools and ideas related to Blokky, and what Blokky takes from each or deliberately leaves out. It defines nothing; the language is defined by the normative files listed in the [overview](overview.md#7-reading-guide).

The descriptions are short and kept to what is well established about each tool. They are not complete, and other tools change over time; check their own documentation for details.

## 1. Plain shell

**What it is.** A bash (or PowerShell) script with `set -euo pipefail`, `timeout`, `trap … EXIT`, `mktemp -d`, background jobs with `&` and `wait`, and loops with `sleep`. This is what agents write today, and it is Blokky's security baseline: a plan must never be less safe than the equivalent shell, and should be easier to review.

**Takes.** Shells stay the leaves: a `script` node runs shell text as written, and `exec` runs a program the way a shell would after parsing. Exit codes keep their meaning (0 is success, `ok_exit` lists more).

**Leaves.** Control flow written in shell syntax, implicit word splitting and globbing of variables, and cleanup that depends on `trap` firing. In a plan, variables reach commands only as whole argv elements or environment variables, and cleanup is `finally`, which runs after failure, timeout and cancellation.

## 2. Ansible

**What it is.** A configuration-management and automation tool. Playbooks are YAML lists of tasks, each calling a module, run against an inventory of hosts. Relevant constructs: `block` with `rescue` and `always`; `register` to keep a task's result; `until` with `retries` and `delay` to repeat a task until a condition holds; loops (`loop`, and the older `with_items`); `when` guards; `ignore_errors`; and the `command` module (argv, no shell) next to the `shell` module (runs through a shell). Values and conditions are Jinja2 templates and expressions.

**Takes.** The overall shape: a YAML tree of tasks with keywords that wrap them. `block`/`always` became `do` with `finally`; `register` became `capture`; `until`/`retries`/`delay` became `until`/`max`/`every` (and `retry`); `with_items` became `for`; `when` and `ignore_errors` kept their names. The `command`/`shell` split became `exec`/`script`.

**Leaves.**

- **Templating.** Jinja2 can appear almost anywhere, including in commands. Blokky has no expression language: conditions are one subject and one operator, `${X}` appears only in display strings and `set`/`vars` templates, and executed text is never interpolated.
- **`rescue`.** A rescue section that runs only after a failure is approximated by `any` (an ordered fallback: try the first child, and only if it fails, the next) and by `retry` conditions; there is no separate rescue keyword.
- **Hosts, inventory, modules, facts, idempotence and "changed" state.** Blokky runs commands on the machine it is invoked on and knows only exit codes and output.
- **YAML 1.1 implicit typing.** In a plan every scalar is a string, and booleans are exactly `true`/`false`.

## 3. duckflux

**What it is.** A YAML workflow DSL aimed at orchestrating multi-step and multi-agent pipelines, with its own runtime. Steps have types such as shell execution, HTTP calls and sub-workflows; the flow has loops (`until` with `max`), parallel steps, `if`/`then`/`else`, `when` guards, retries with backoff, per-step timeouts, events, and workflow inputs and outputs. Conditions and mappings use Google's CEL expression language, and step outputs are passed along the flow.

**Takes.** Confirmation that a small, declarative YAML layer with first-class loops, parallelism, guards and timeouts is a natural fit for agent work, and that execution order belongs in the document rather than in an agent's improvisation.

**Leaves.** An expression language (Blokky uses fixed subjects and operators instead of CEL), HTTP and other non-process step types (in Blokky everything that runs is a process), events, and orchestration of agents themselves. Blokky is meant to be *called by* an agent for one well-scoped job, not to drive agents.

## 4. execline

**What it is.** A non-interactive scripting language by Laurent Bercot (skarnet.org). An execline script is parsed once into an argv; each command runs its work and then executes the rest of its argv ("chain loading"), so there is no long-lived interpreter and no shell parsing at run time. Control flow (`if`, `foreground`, `background`, loops) and variable substitution are themselves small programs that rewrite argv.

**Takes.** The conviction that commands should be argv, not text re-parsed by a shell, and that what will run should be determinable before it runs. `exec` arrays, the shell-free `exec` string form, and "every `{ var: X }` element is exactly one argument" follow the same idea.

**Leaves.** The chain-loading execution model and argv rewriting as the means of substitution. Blokky is a tree evaluated by one runtime that supervises its processes, because timeouts, cancellation, cleanup and a structured result need a supervisor. Its YAML surface trades execline's compactness for readability by agents and reviewers.

## 5. Argv-as-JSON runners

**What it is.** A common pattern rather than one tool: a command is given as a JSON array of strings (`["git", "log", "-n", "5"]`) and run directly, without a shell. The Docker `CMD`/`ENTRYPOINT` "exec form", process-spawning APIs that take an argument list, and agent tools that accept a structured command instead of a shell string all work this way.

**Takes.** The canonical `exec` form is exactly this: a list whose elements become argv one to one. It removes quoting, word splitting and shell operators from the picture, and makes each command easy to match against permission rules.

**Leaves.** A bare argv has no control flow. Blokky adds structure around argv leaves instead of encoding control flow in the strings.

## 6. Agent command-safety tools

**What it is.** Tools that sit between an agent and the shell to decide what may run: permission rules in agent runners (allow and deny lists, prefix matching), pre-execution hooks, wrappers that intercept or parse commands, and approval queues such as agent-safe-runner, where an agent submits a command, a policy assesses it, a person approves it, and the run is audited.

**Takes.** The problem statement: agents' commands need to be reviewed, and compound shell commands are hard to review or match against rules. Blokky's answer is to make plans easy to inspect: everything a plan can execute is determinable before it runs, so an implementation can list every process, argv and environment entry for a runner's rules, a hook or an external validator.

**Leaves.** Being the control. Blokky does not decide what is allowed, does not queue or approve commands and is not a sandbox; the runner's permission system and the implementation's approval mechanisms do that. Controls that only work if agents can use *only* Blokky are out of scope, because agents keep a generic shell tool.

## 7. CI step controls (GitHub Actions)

**What it is.** CI workflow files describe jobs and steps. In GitHub Actions: `timeout-minutes` on a job or step; `continue-on-error` so a failing step doesn't fail the job; `if:` conditions with `${{ … }}` expressions; and `strategy.matrix` (with `include`/`exclude`, `fail-fast` and `max-parallel`) to run a job once per combination of values.

**Takes.** Per-step `timeout`, `ignore_errors` (the counterpart of `continue-on-error`), `for: { matrix }` with fail-fast and a concurrency limit, and the habit of guarding a step with a condition.

**Leaves.**

- **Textual expressions in scripts.** In Actions, `${{ … }}` inside a `run:` script is substituted into the script text before the shell sees it, which makes untrusted values a script-injection risk. Blokky never interpolates executed text; values reach scripts as environment variables.
- **`if:` on a step.** Blokky's `if` is a node kind with `then`/`else`; a guard on a node is `when`. A GitHub-style `if:` next to another kind gets a targeted error suggesting `when`.
- **`include`/`exclude` for matrices** (combinations are skipped with a `when` in the body instead), runners, artifacts, caching, triggers and hosted execution. Blokky is not a CI system.

## 8. Task runners: make, just, Taskfile

**What it is.** Tools that name tasks (targets, recipes) and run their commands, with dependencies between tasks. `make` decides what to rebuild from file timestamps; `just` is a command runner with parameters and recipes; Taskfile (go-task) defines tasks in YAML, with dependencies that run in parallel, variables and up-to-date checks.

**Takes.** Little directly. They show that named, reviewable units of commands are useful, and a plan can call a task runner as a leaf.

**Leaves.** Named, reusable tasks and dependency graphs. A plan is one tree run once; repeated work is written as a plan file and run again. Task runners are the right tool for a project's standing commands; Blokky is for the one-off control flow around them.

## 9. Single-purpose utilities: timeout(1), flock(1)

**What it is.** `timeout` (GNU coreutils) runs a command and sends it a signal after a duration, optionally followed by a kill after a further delay (`-k`). `flock` (util-linux) runs a command while holding an advisory lock on a file, waiting for it or giving up (`-n`, `-w`); the lock is released when the holder exits.

**Takes.** The semantics: `timeout` with a graceful signal and then a forced kill after a grace period, and `lock` as a named, exclusive advisory lock that is released when the run's process dies, so a crashed run never leaves a lock behind.

**Leaves.** Composing them by nesting command lines. In a plan they are modifiers that combine in a fixed order with everything else, and a timeout stops the leaf's whole process tree.

## 10. Service dependencies: Docker Compose

**What it is.** Compose files declare services; `depends_on` orders their startup, and with `condition: service_healthy` a service waits until another one's `healthcheck` (a command run at an interval, with a timeout and a number of retries) reports healthy.

**Takes.** The `services` modifier: background processes that start in dependency order (`depends_on`), each with a required readiness condition (`ready:`, for example an open port or a line in the output), that live as long as one node and are stopped afterwards in reverse order.

**Leaves.** Containers as the unit of a service (a Blokky service is a process; `container` is a separate modifier), networks, volumes, restart policies and long-running stacks. Services exist only for the duration of one node.

## 11. Workflow engines

General-purpose workflow and orchestration systems (data pipelines, durable workflow runtimes, Kubernetes-native workflow controllers) offer durable state, scheduling, distribution across machines and rich expression languages. Blokky deliberately has none of these: it is a single-run, single-machine language for the control flow around a few commands, small enough to read at a glance.
