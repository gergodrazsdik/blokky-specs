# Overview

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is **informative**. It introduces Blokky for a first-time reader, human or agent: the problem it addresses, the mental model, an annotated example, when to use it and when not to. It defines nothing. Where it seems to disagree with the normative files ([syntax.md](syntax.md), [reference.md](reference.md), [execution-model.md](execution-model.md), [variables.md](variables.md), [conditions.md](conditions.md), [shells.md](shells.md), [containers-and-privilege.md](containers-and-privilege.md), [errors.md](errors.md), [results.md](results.md) and the schema `schema/blokky.schema.json`), they win.

## 1. The problem

Coding agents run a lot of shell. Much of it is not the work itself but the scaffolding around it:

- a timeout, so a hung command doesn't block the session;
- a retry loop for a flaky download or a slow service;
- a polling loop that waits for a CI run, a deployment or a port;
- a temporary directory, and the `rm -rf` that cleans it up;
- a background process plus a `trap` that kills it afterwards;
- a few commands in parallel, with "if one fails, stop the others".

Written by hand, this scaffolding is long and easy to get subtly wrong: an unquoted variable, a `trap` that doesn't fire on timeout, a loop with no upper bound, a child process left running, a `$?` read one command too late. It is also hard to review: the interesting command is buried in twenty lines of control flow. And it interacts badly with permission systems. A runner can allow `gh run view` and still has to ask about a compound command that wraps it in `for`, `sleep`, `timeout` and `&&`; a cleanup `rm -rf "$tmp"` triggers its own approval prompt.

Blokky moves that scaffolding into a small declarative layer. The plan says "retry this three times", "wait until that holds, at most five minutes", "run these in parallel", "do this in a fresh temp directory"; the commands at the leaves stay simple, single-purpose and easy to check one by one. The runtime owns the temp directories, scripts and capture files it creates, so cleaning up never needs a hand-written `rm -rf`.

## 2. The mental model

### 2.1 A plan is a tree of nodes

A **plan** is a YAML document: a root mapping with a few plan-only keys (`blokky:`, `inputs:`, `vars:`, `outputs:`, `defaults:`) and one root **node**. Every node has exactly one **kind**:

| Group | Kinds | What they do |
|---|---|---|
| Leaves | `exec`, `script` | Run a process: a program with an argv array (no shell), or shell text written to a file and run with a named shell. |
| Groups | `do`, `all`, `any`, `race`, `if` | Run child nodes: in sequence, in parallel (all must succeed), until one succeeds, until the first one completes, or one branch of a condition. |
| Simple nodes | `sleep`, `log`, `fail`, `assert`, `set` | Wait, record a message, fail on purpose, fail unless a condition holds, bind variables. They start no process. |

`exec` is the primitive. A `script` leaf compiles to an `exec` of its shell with the script file, so everything a plan runs is ultimately a program and its argv.

### 2.2 Modifiers wrap a node

Around its kind, a node can carry **modifiers** that scope, repeat, limit or label it: `name`, `when`, `timeout`, `lock`, `tempdir`, `cwd`, `env`/`export`, `container`, `become`, `services`, `finally`, `ignore_errors`, a repetition (`retry`, `while`, `until` or `for`) and `attempt_timeout`. Leaves also take leaf options such as `capture`, `stdin` and `ok_exit`.

Modifiers always apply in the same order, outermost first, whatever order they are written in:

`when` → `timeout` → `lock` → `tempdir` → `cwd` → `env` → `container`/`become` → `services` → `finally` → repetition → `attempt_timeout` → kind

So you can read a node from the outside in: "if this holds, within this time, holding this lock, in a fresh temp dir, with this environment, …, retry up to three times, each attempt at most a minute, run this." A few consequences follow directly from the order: a `timeout` covers every retry; `finally` runs once per node, not once per attempt; a node skipped by `when` takes no lock and runs no cleanup. A "block" in Blokky is just a `do` node with modifiers. There is at most one repetition per node; combinations are written by nesting.

### 2.3 Conditions

`if`, `when`, `assert`, `while`, `until`, `retry` and service readiness all use one condition construct: a **subject** (`var`, `env`, `path`, `host`, `result`, `probe`) plus one **operator** (`equals`, `in`, `contains`, `matches`, `empty`, `defined`, `exists`, `gt`, …), or the composites `all`, `any` and `not`:

```yaml
{ var: STATUS, in: [queued, in_progress] }
{ path: package-lock.json, exists: true }
{ probe: { exec: [docker, info] } }
```

Blokky evaluates every subject itself without starting a process, except `probe`, which runs a short command and looks at its exit code or output. A condition that can be neither true nor false (an undefined variable, a number that isn't a number) is a **condition error** and fails its node; it never silently counts as false. There is no expression language: a check that needs more than a subject and an operator is a probe.

### 2.4 Variables

Plan **variables** are bound by the plan: **inputs** given by the caller, plan constants in **`vars`**, **`set`** nodes, **captures** of a leaf's stdout, loop variables and temp-dir paths. Their names are upper case (`RUN_ID`). Every variable is bound **once**; rebinding or shadowing a name is an error.

Plan variables and environment variables are separate. A plan variable reaches a command only explicitly:

- as one whole argv element of an `exec` array: `exec: [gh, run, view, { var: RUN_ID }]`;
- as an environment variable: `env: { RUN: { var: RUN_ID } }` or `export: [RUN_ID]`.

There is no shell interpolation of variables. Executed text (`script` bodies, `exec` strings, probe commands) is taken literally; `${X}` is only expanded in display strings (`name` and the messages of `log`, `fail` and `assert`) and in `set`/`vars` templates, which build a string but never execute it. A `script` that needs a value reads it from the environment (`"$RUN"` in bash), so a value is never parsed as shell syntax.

Secrets come only by reference (`{ from_env: GH_TOKEN, secret: true }`, or a capture marked `secret: true`) and are masked in what an implementation shows. Masking is hygiene, not secrecy.

### 2.5 The run result

A run ends with a **run result**: the run's status (`succeeded`, `failed` or `stopped`), the inputs and outputs, and one result per node, in plan order, with its status (`succeeded`, `failed`, `skipped`, `timed_out`, `cancelled`), attempts or iterations, timings and errors with machine-readable codes (`BK_TIMEOUT_TOTAL`, `BK_LOOP_MAX_REACHED`, or your own codes from `fail` and `assert`). It is designed to be read by an agent: structured, sized for a context window, and the same shape every time. How it is serialized is up to the implementation; [results.md](results.md) gives the abstract model.

## 3. An example: wait for CI

An agent has pushed a branch and wants to wait for its CI run. Without Blokky that is a polling loop to find the run, a timeout around `gh run watch`, and a second, parallel check that gives up if the run sits in the queue for too long, each with its own `sleep`, counter, background process and `kill`. As a plan:

```yaml
blokky: 1.0
name: wait for CI on ${BRANCH}
inputs:
  BRANCH:
    description: Branch whose CI run to wait for
    matches: '^[A-Za-z0-9._/][A-Za-z0-9._/-]*$'
outputs: [RUN_ID]
do:
  - name: find run id
    exec: [gh, run, list, -b, { var: BRANCH }, -L1, --json, databaseId, -q, '.[0].databaseId']
    capture: RUN_ID
    until: { result: stdout, matches: '^\d+$' }
    every: 10s
    timeout: 2m
  - log: "Watching CI run ${RUN_ID}"
  - all:
      - name: watch run
        exec: [gh, run, watch, { var: RUN_ID }, --exit-status]
        timeout: 45m
      - name: queued guard
        exec: [gh, run, view, { var: RUN_ID }, --json, status, -q, .status]
        until: { result: stdout, not_equals: queued }
        every: 15s
        timeout: 5m
```

How it reads:

- **`blokky: 1.0`** names the language version. **`inputs:`** declares one required string input, `BRANCH`, constrained by a single-quoted regex (which also rules out a value starting with `-`). The caller supplies it (for blokky-cli: `--input BRANCH=feature/x`); the plan never prompts for it. **`outputs:`** publishes `RUN_ID` in the run result.
- The root node is a **`do`**: its children run in order, and the first failure stops it.
- **find run id** runs `gh run list` with the branch as one argv element: no quoting, no word splitting. `until` repeats it every 10s until its stdout looks like a run id; `timeout: 2m` bounds the whole loop. `capture: RUN_ID` binds the trimmed stdout of the iteration that ended the loop.
- **`log`** records a message in the run result; `${RUN_ID}` is interpolated because a log message is a display string.
- **`all`** runs its two children in parallel. **watch run** follows the run for at most 45 minutes and fails if the run fails (`--exit-status`). **queued guard** polls the run's status and succeeds once it has left the queue; if it is still queued after 5 minutes, the guard times out, and because `all` is fail-fast by default, the watch is cancelled and the whole plan fails with the guard's timeout as its cause.

Every process this plan can start is visible in the plan: three `gh` commands with known argv, where only `BRANCH` and `RUN_ID` are filled in at run time. A reviewer, or a permission rule, can judge them one by one.

## 4. When to use Blokky

Blokky pays off when the scaffolding is a large part of what you would otherwise write:

- waiting and polling: CI runs, deployments, ports, files appearing, queues draining;
- retries with a bound and a delay, optionally only for certain failures;
- timeouts on individual steps and on the whole job, with reliable killing of whole process trees;
- parallel steps with fail-fast, or "first one to succeed wins";
- work in a temporary directory, cleanup that runs even after failure or timeout, background services (a database, a dev server) that live exactly as long as a step;
- loops over files, list items or JSON output, sequential or with bounded parallelism.

## 5. When not to use it

- **One simple command.** `git status` or `dotnet test` with no timeout, retry or cleanup needs no plan. Run it directly.
- **Interactive work.** Leaves never read the terminal; stdin is empty unless the plan supplies it. Anything that prompts, opens an editor or needs a password belongs outside Blokky. Blokky never prompts for, accepts or forwards passwords.
- **Real programming.** If you need arithmetic, string manipulation beyond joining, data structures, functions or non-trivial logic, write a script in a real language (Python, PowerShell, bash) and run it as a leaf. Conditions deliberately have no expression language, and templates deliberately have no functions.
- **Long-lived automation.** Scheduled jobs, pipelines across machines, deployment orchestration with state are the job of CI systems and workflow engines.

## 6. What Blokky is not

- **Not a sandbox.** Running a plan is equivalent to running the same commands in bash: it grants no capability, bypasses no permission system and hides nothing that will run. A hostile plan is as dangerous as a hostile script. Agents keep their generic shell tool; Blokky is an additional tool, not a replacement.
- **Not a control.** Deciding what may run is the job of the agent runner's permission system and the implementation's approval mechanisms. Blokky's warnings, strict YAML rules and secret masking make plans cleaner and easier to review; they are hygiene and are never presented as enforcement. Resource bounds (timeouts, concurrency caps) exist for predictability, not as security boundaries.
- **Not a CI system.** It runs on the machine it is invoked on, for one run, and keeps no state between runs except what the implementation keeps for cleanup and review.
- **Not a general workflow engine or a scripting language.** It has no expression language, no functions, no mutable variables and no way to generate plan structure at run time. A feature that would need those probably doesn't belong.

What Blokky does aim for is **reviewability**: everything a plan can execute is determinable from the plan and its inputs before it runs, so an implementation can list every process, argv and environment entry for a human, a classifier or a validator. The goal is "never less safe than the equivalent bash, and easier to review".

## 7. Reading guide

| If you want to … | Read |
|---|---|
| Look up a term | [glossary.md](glossary.md) |
| Write a plan: YAML rules, the root document, inputs, value forms, pitfalls | [syntax.md](syntax.md) |
| Know what each kind and modifier does, and which combinations are valid | [reference.md](reference.md) |
| Understand modifier order, start order, timeouts, cancellation and statuses | [execution-model.md](execution-model.md) |
| Bind and pass values: inputs, `vars`, `set`, captures, scope, secrets | [variables.md](variables.md) |
| Write conditions and probes | [conditions.md](conditions.md) |
| Know how `exec` strings are split and how each shell is invoked | [shells.md](shells.md) |
| Run leaves in containers or as another user | [containers-and-privilege.md](containers-and-privilege.md) |
| Handle errors by code | [errors.md](errors.md) |
| Know what a run reports | [results.md](results.md) |
| See how Blokky relates to other tools | [prior-art.md](prior-art.md) |
| Know why a decision was made | [adr/](../adr/README.md) |

The plan schema (`schema/blokky.schema.json`) is normative for structure; [reference.md §8](reference.md#8-rules-the-schema-doesnt-express) lists the rules it can't express. The security considerations are in [reference.md §9](reference.md#9-security-considerations).
