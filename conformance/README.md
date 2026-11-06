# Conformance suite

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is normative for the **conformance suite**: the case format, the layout of `cases/`, per-platform overrides, timing, the pairwise policy for modifier combinations, the contract a runner fulfils to run the suite, and how rule coverage is measured. The fake programs that cases run are specified in [testkit-interface.md](testkit-interface.md). Normative keywords are used as defined in [syntax.md §1](../spec/syntax.md#1-conventions). Rules carry IDs (`CF-n`).

The cases themselves are written after the language review ([ADR 0013](../adr/0013-scope-and-versioning.md)); `cases/` is empty until then.

## 1. Purpose and principles

The suite tests what a plan means and what it can observe, independently of any implementation. An implementation (the reference one is blokky-cli) runs it with its own runner; the share of cases that pass measures how much of the language it implements.

- **CF-1.** Cases are **implementation-independent**. They assert on the abstract run result ([results.md](../spec/results.md)) and on plan and input errors ([errors.md](../spec/errors.md)), never on an implementation's report format, messages, exit codes, file layout or configuration.
- **CF-2.** Each implementation provides an **adapter** that runs a plan and maps its own output (for blokky-cli: the JSON run report) to the **result document** (§3.6), the form of the run result that cases are matched against. Mapping is the adapter's only job: it MUST NOT repair, reorder or infer anything the implementation didn't record.
- **CF-3.** Cases never assert on human-readable messages (results.md §5) or on non-deterministic fields (results.md §6) except through the tolerances and matchers of this document.
- **CF-4.** Cases don't depend on real tools. Every process a case starts is the testkit ([testkit-interface.md](testkit-interface.md)) or a shell the case lists under `requires` (§3.2).
- **CF-5.** Each case tests a small number of rules and cites them (§7). A case that fails points at the rules it cites.

## 2. Layout

```text
conformance/
  README.md                 # this document
  testkit-interface.md      # the fake programs
  cases/
    syntax/                 # one directory per spec file …
    variables/
    conditions/
    reference/
    execution-model/
    shells/
    containers-and-privilege/
    results/
    errors/
    combinations/           # … plus the pairwise modifier cases (§6)
```

- **CF-6.** Every case is **one YAML file** under `cases/<area>/`, where `<area>` is the spec file (without `.md`) that holds the case's primary rule, or `combinations` for the cases of §6. Subdirectories below an area are allowed (`reference/for/`).
- **CF-7.** File names are lowercase kebab-case ending in `.yaml` (`timeout-grace-after-limit.yaml`). The case **id** is the file's path below `cases/` without the extension (`execution-model/timeout-grace-after-limit`). Ids are stable: a case that is removed leaves its id unused; a case that changes meaning gets a new id.
- **CF-8.** Case files are YAML 1.2 and pass the repository's `yamllint --strict`, which asks for the spec's flow style everywhere: one space inside flow mappings (`{ code: BK_EXIT }`, `{ var: X }`). Unlike plans, case files use YAML's ordinary typing: `3` is an integer, `true` a boolean. A plan embedded in a case is a string (§3.3) and keeps the plan's own rules.

## 3. Case format

### 3.1 Keys

| Key | Required | Value |
|---|---|---|
| `title` | yes | One line: what the case shows. |
| `rules` | yes | Rule IDs the case tests (`[EM-26, EM-27]`); at least one, or `spec` instead (§7). |
| `spec` | no | References to normative text without rule IDs: `<file>.md§<section>` (`syntax.md§3.1`). |
| `features` | yes | The features the plan uses (§3.2). |
| `requires` | no | Environment requirements (§3.2). |
| `clock` | no | The clock modes the case is valid in (§5); default `[real, scaled]`. |
| `plan` | one of | The plan text, as a literal block scalar (§3.3). |
| `plan_base64` | one of | The plan bytes in base64, for plans that aren't valid UTF-8 or need exact bytes (BOMs, CR, tabs). |
| `inputs` | no | Input values, as a list of `NAME=VALUE` strings (§3.4). |
| `env` | no | Environment variables added to the base environment (§8.2), as a mapping of strings. |
| `files` | no | Files and directories to create in the work directory before the run (§3.4). |
| `programs` | no | Testkit aliases to put on `PATH` (§3.4). |
| `actions` | no | Runner actions during the run, such as an external stop (§3.4). |
| `expect` | yes | The expected outcome (§3.5). |
| `platforms` | no | Per-platform skips and overrides (§4). |
| `notes` | no | Free text for readers; never interpreted. |

- **CF-9.** The key list is closed: a runner MUST reject a case with an unknown top-level key as a broken case (reported as `error`, §8.4), so typos don't silently weaken a case.
- **CF-10.** The case's id comes from its path (CF-7); a case file doesn't repeat it.

### 3.2 Features and requirements

**Features** let an implementation that supports only part of the language run the cases it can.

- **CF-11.** `features` lists every language feature the plan uses, with the ids of the table below. A runner MAY derive the list from the plan to check it; the suite's own checks SHOULD.
- **CF-12.** The adapter declares which feature ids its implementation supports. The vocabulary below is a proposal; pinning it, and using it for `BK_PLAN_NOT_SUPPORTED`'s `detail.feature`, is pending (tracker F-0010). A case whose `features` include one that isn't supported is **skipped** with the reason `not supported: <feature>` (§8.4), and the runner SHOULD run the **not-supported check** instead: the implementation MUST reject the plan in validation with `BK_PLAN_NOT_SUPPORTED`, and no process may start (EM-1). The check passing keeps the case a skip; anything else is a fail.

| Group | Feature ids |
|---|---|
| Kinds | `exec`, `exec-string` (string form), `script`, `do`, `all`, `any`, `race`, `if`, `sleep`, `log`, `fail`, `assert`, `set` |
| Shells (`script`, probes, services) | `shell-bash`, `shell-sh`, `shell-pwsh`, `shell-powershell`, `shell-zsh`, `shell-fish` |
| Leaf options | `stdin`, `ok-exit`, `stderr-merge`, `encoding`, `max-log-bytes`, `keep-descendants`, `capture`, `capture-fields`, `capture-file`, `secret` |
| Modifiers | `when`, `timeout`, `lock`, `tempdir`, `cwd`, `env`, `export`, `container`, `become`, `services`, `finally`, `ignore-errors`, `attempt-timeout` |
| Repetition | `retry`, `retry-condition`, `backoff`, `jitter`, `while`, `until`, `for-each`, `for-count`, `for-glob`, `for-items`, `for-lines`, `for-matrix`, `for-concurrency`, `collect` |
| Conditions | `cond-var`, `cond-env`, `cond-path`, `cond-command`, `cond-host`, `cond-result`, `cond-probe`, `cond-json`, `cond-numeric`, `cond-composite` |
| Values | `from-env`, `secret-ref`, `interpolation` |
| Plan-level | `inputs`, `vars`, `outputs`, `defaults` |
| Runner | `external-stop` (§3.4 `actions`) |

New ids are added with the language features they name; an id is never reused for something else.

**Requirements** say what the machine must provide, independently of the implementation:

| Key | Value |
|---|---|
| `os` | A list of `linux`, `macos`, `windows`: the case runs only there. Prefer `platforms` (§4) for small differences. |
| `shells` | Shells that MUST be installed (`[bash]`, `[pwsh]`). |
| `ports` | Loopback TCP ports the case listens on (`services` with `ready: { port }`). |
| `privilege` | `root` (the run has root privileges) or `passwordless-elevation` (`sudo -n` or `doas -n` works), for `become`. |
| `container-engine` | `true`: a container engine is available, for `container`. |

- **CF-13.** A case whose requirements aren't met is skipped with the reason `requirement: <key>`. Requirements never make a case pass.
- **CF-14.** Because `port` values and `lock` names are literal in plans, cases that use them MUST be unique suite-wide: ports come from the range 47000–47999 and are listed in `requires.ports`; lock names start with `conf-` followed by the case's file name. A runner MUST NOT run two cases that list the same port at the same time.

### 3.3 The plan

- **CF-15.** `plan` holds the plan text exactly as it is passed to the implementation: a YAML literal block scalar (`plan: |`), so the plan's line numbers are the block's lines counted from 1. The plan is not parsed as part of the case file.
- **CF-16.** Plans in cases use canonical forms: `blokky: 1.0`, argv arrays, block-scalar scripts, mappings in flow or block style as in the spec. A case that tests a non-canonical form (an `exec` string, a quoting pitfall) says so in its `title`.
- **CF-17.** Programs are the testkit (`exec: [blokky-testkit, …]`), a testkit alias from `programs`, or a shell listed in `requires.shells`.

### 3.4 Inputs, environment, files and actions

- **CF-18.** `inputs` is an ordered list of `NAME=VALUE` strings, split at the first `=`, passed to the implementation in order with the transport the adapter uses (for blokky-cli: `--input`). A string without `=` is passed unsplit, for `BK_INPUT_SYNTAX` cases. Transport-specific checks (for example the MCP JSON types of VA-15) are out of scope for the suite.
- **CF-19.** `env` values are added to the base environment (§8.2), replacing a variable of the same name. A value of `null` removes the variable from the base environment.
- **CF-20.** `files` maps a path relative to the work directory to its content. A string value is the content as UTF-8 (no newline added). A mapping value has `text` or `base64`, plus optional `executable: true` (mode 0755 on Unix; ignored on Windows); `{ dir: true }` creates a directory. Parent directories are created as needed. Paths use `/` on every platform.
- **CF-21.** `programs` maps an alias name to the testkit arguments it stands for: `programs: { git: [print, --out, 'git version 2.0'] }` puts an executable named `git` on `PATH` that behaves like `blokky-testkit print --out 'git version 2.0'` followed by its own arguments ([testkit-interface.md](testkit-interface.md), TK-6).
- **CF-22.** `actions` is a list of `{ after: <duration>, stop: true }` entries: at the given time after the run starts, the runner stops the run from outside (EM-55 to EM-57) with the means the adapter provides. Cases with `actions` list the `external-stop` feature. The stop cause is implementation-defined, so cases assert on `status: stopped` and the nodes, not on `stop_cause`.

### 3.5 Expectations

`expect` describes either a **validation outcome** or a **run outcome**.

**Validation outcome:**

| Key | Meaning |
|---|---|
| `plan_errors` | The plan errors the implementation MUST report. Each entry: `code`, optional `detail` (subset), optional `line` and `column` (1-based, in the plan text). |
| `input_errors` | The same for input errors (no position). |
| `exhaustive` | `true`: no errors other than the listed ones may be reported. Default `false`. |

- **CF-23.** For a validation outcome the run MUST end in validation (EM-1): no run result, and no process started, which the runner checks with the testkit's invocation log (TK-5). Each listed error MUST be matched by a distinct reported error, in any order (EM-2 reports them together, in no fixed order).
- **CF-24.** A plan error's `line` and `column` point at the offending key, or at its value when the value is what is wrong ([syntax.md §1](../spec/syntax.md#1-conventions)). Cases give `line` for every plan error whose offending key or value is unambiguous, and `column` where the token is too. `detail.rule` is asserted for every `BK_PLAN_INVALID`.

**Run outcome:**

| Key | Meaning |
|---|---|
| `status` | The run status: `succeeded`, `failed` or `stopped` (required for a run outcome). |
| `error` | The run's primary error (§3.6), or `null` for none. |
| `outputs` | Expected outputs by name: a string, `null` (unbound) or `{ $secret: true }`. |
| `nodes` | Expected node results, keyed by path id (§3.6). |
| `invocations` | Expected testkit invocations from the invocation log (TK-5). |
| `files` | Expected files in the work directory after the run: `{ exists: false }`, or `text`/`base64`/`contains`. |
| `duration` | The run's duration (§5), usually `{ $min: …, $max: … }`. |

- **CF-25.** A case's `expect` holds a validation outcome or a run outcome, never both. A plan that validates and then fails at run time is a run outcome.

### 3.6 The result document and path ids

The result document is the run result of results.md, written with these keys. Values are strings, integers, booleans, `null`, lists and mappings.

| results.md | Key | Notes |
|---|---|---|
| run: status, stop cause, error, outputs | `status`, `stop_cause`, `error`, `outputs` | |
| run: inputs | `inputs` | `{ NAME: { value, source } }`, `source` is `supplied` or `default`. |
| node: id, kind, name, status | `id`, `kind`, `name`, `status` | `name` is the raw template. |
| node: ignored, skip reason | `ignored`, `skip_reason` | `skip_reason`: `condition` or `not_reached`. |
| node: repetition | `repetition` | `{ count, ended_by, last_condition, entries: [{ index, name, item, status, error }] }`; `item` is a string, or a mapping for `matrix`. |
| node: finally | `finally_status` | The `finally` list's nodes have their own path ids. |
| node: lock wait | `lock_wait` | A duration (§5). |
| node: services | `services` | `[{ name, ready_after, ended, exit_code }]`; `ended` is `stopped`, `exited` or `never_ready`; `ready_after` is a duration from the node's start. |
| node: messages | `messages` | `[{ text, level }]`, `text` rendered and masked. |
| node: probes | `probes` | `[{ invocation, exit_code, result }]`. |
| node: bindings | `bindings` | A list of names. |
| leaf fields | `program`, `invocation`, `exit_code`, `signal`, `killed_by`, `descendants_held_output`, `survivors`, `user`, `container` | `invocation` is the masked argv; `signal` is a name (`SIGKILL`); `user` is `{ name, elevation }`. |
| error: code, node, detail, causes, context | `code`, `node`, `detail`, `causes`, `context` | `message` is never matched (CF-3). |
| durations (results.md §6) | `duration` | On the run and on every node. |

- **CF-26.** Nodes are addressed by **path id** ([reference.md §1](../spec/reference.md#1-node-anatomy)): the root is `/`, and a node in a body field is its parent's id plus `/<field>/<index>`, 0-based (`/do/2/all/0`, `/do/3/then/1`, `/finally/0`). `expect.nodes` is a flat mapping from path id to the node's expected fields; children are asserted under their own ids, not nested.
- **CF-27.** Nodes inside a loop body keep their plan path id; iterations are told apart by their index (reference.md §1). Until results.md gives per-iteration results for body nodes, cases assert on them through the repeating node's `repetition.entries` (by `index`), captures, `collect` and the invocation log.

### 3.7 Matching

- **CF-28.** **Mappings match as subsets:** only the keys a case lists are checked; the result may hold more (RS-4). This applies to `expect.nodes`, node fields, `detail`, `context` and `outputs`.
- **CF-29.** **Lists match exactly and in order**, element by element, unless wrapped in a matcher (`$unordered`, `$contains`). `causes` lists are ordered by the spec (results.md §5), so they are matched in order.
- **CF-30.** **Scalars match by value.** An integer and its decimal string are equal (`3` matches `'3'`), so exit codes can be written either way. Durations are compared as durations (§5). Strings are compared exactly, after the adapter has decoded them; no trimming or case folding.
- **CF-31.** `null` matches only a field that is present with no value; `{ $absent: true }` matches a field or node that isn't there.

Matchers are single-key mappings whose key starts with `$`:

| Matcher | Matches |
|---|---|
| `{ $absent: true }` | A field, output or path id that isn't present. |
| `{ $present: true }` | Any value, as long as the field is present. |
| `{ $regex: 'pattern' }` | A string containing a match (unanchored). Patterns use only syntax that .NET, ECMAScript and RE2 share: no lookaround, no backreferences. |
| `{ $one_of: [a, b] }` | Any of the listed values (each matched by these rules). |
| `{ $min: X, $max: Y }` | A number or duration in the closed range; either bound may be left out. The only matcher with two keys. |
| `{ $unordered: [...] }` | A list of the same length whose elements match the listed ones one-to-one, in any order. |
| `{ $contains: [...] }` | A list in which each listed element matches a distinct element, in any order; other elements are allowed. |
| `{ $count: N }` | A list of length N (N may be a `$min`/`$max` matcher). |
| `{ $secret: true }` | An output marked secret, without a value (VA-47). |

- **CF-32.** A runner reports the first mismatch as a path into the expectation (`nodes./all/0.error.code: expected BK_TIMEOUT_TOTAL, got BK_CANCELLED`).

### 3.8 Example

A run case: a stubborn leaf ignores the graceful stop, so it is killed only after the grace period, which starts after its own `timeout` fired.

```yaml
title: The grace period follows a fired timeout, and the node is timed_out
rules: [EM-26, EM-27, EM-43, EM-50, EM-66]
features: [all, exec, timeout]
plan: |
  blokky: 1.0
  name: grace after limit
  all:
    - name: stubborn
      timeout: 2s
      exec: [blokky-testkit, sleep, 1m, --ignore-term]
    - exec: [blokky-testkit, exit, '0']
expect:
  status: failed
  error: { code: BK_TIMEOUT_TOTAL, node: /all/0 }   # the group carries its child's error (EM-66)
  nodes:
    /:
      kind: all
      status: failed
      error: { code: BK_TIMEOUT_TOTAL, node: /all/0 }
    /all/0:
      status: timed_out
      killed_by: timeout
      error: { code: BK_TIMEOUT_TOTAL, node: /all/0 }
      duration: { $min: 7s, $max: 12s }   # 2s timeout + 5s grace
    /all/1:
      status: succeeded
      exit_code: 0
  invocations:
    $unordered:
      - { argv: [sleep, 1m, --ignore-term] }
      - { argv: [exit, '0'] }
platforms:
  unix:
    expect:
      nodes:
        /all/0: { signal: SIGKILL }
  windows:
    expect:
      nodes:
        /all/0: { signal: { $absent: true } }
```

A validation case: an `until` loop with neither `max` nor `timeout`.

```yaml
title: An unbounded until loop is a plan error
rules: [RF-5]
features: [until, exec, capture, cond-var]
plan: |
  blokky: 1.0
  until: { var: STATE, equals: done }
  exec: [blokky-testkit, print, --out, done]
  capture: STATE
expect:
  plan_errors:
    - code: BK_PLAN_INVALID
      detail: { rule: bounded-loop }
      line: 2
  invocations: []
```

An input case: a required input that isn't supplied, and an undeclared one.

```yaml
title: A missing required input and an unknown input are reported together
rules: [EM-2, VA-11]
features: [inputs, log, interpolation]
plan: |
  blokky: 1.0
  inputs:
    BRANCH:
      description: Branch to build
  log: "Building ${BRANCH}"
inputs: [BRANCHH=main]
expect:
  input_errors:
    - { code: BK_INPUT_MISSING }
    - code: BK_INPUT_UNKNOWN
      detail: { suggestion: BRANCH }
  exhaustive: true
```

## 4. Per-platform overrides

- **CF-33.** `platforms` maps a platform key to an override. Keys are `unix` (Linux and macOS), `linux`, `macos` and `windows`. An override has `skip` (a reason string: the case is skipped there with `platform: <reason>`), or any of `env`, `files`, `programs`, `requires` and `expect`.
- **CF-34.** Overrides are merged into the case in order of increasing precedence: the case, then `unix`, then the OS key. Mappings merge key by key, recursively; lists and scalars replace; the value `{ $delete: true }` removes a key. `plan` and `inputs` can't be overridden: a plan that must differ per OS uses `host:` branches (CO-7), which are part of what is tested.
- **CF-35.** Typical differences that use overrides rather than separate cases: the graceful stop (SIGTERM vs CTRL_BREAK, EM-26) and the `signal` field (Unix only); exit codes of killed processes; shell availability (`shells.md` §5); path separators in `program` and `invocation` (match those with `$regex`); case-insensitive environment names on Windows (VA-6).
- **CF-36.** A case that tests a rule for one OS only (for example SH-9, Windows command lines) uses `requires.os`, not a `skip` on the others.

## 5. Timing

- **CF-37.** Durations in cases use the plan's duration grammar ([syntax.md §6.5](../spec/syntax.md#65-durations)), plus `0s`. Durations asserted on the result are in **plan time**: the time of the clock the implementation's limits run on (below).
- **CF-38.** Cases assert on timing only with bounds (`$min`/`$max`) and on ordering through statuses, `killed_by`, repetition counts and the invocation log, never on exact values (results.md §6).

### 5.1 Clock modes

Implementations SHOULD let the runner replace the monotonic clock behind every language timer (`timeout`, `attempt_timeout`, `defaults.leaf_timeout`, probe timeouts, `finally_timeout`, `sleep`, `every`, `backoff`, `lock.wait`, `ready_timeout`, readiness polling, the grace period and the reap timeout) with a **test clock**. The suite knows three modes:

| Mode | Plan time is | Support |
|---|---|---|
| `real` | wall-clock time. | MUST |
| `scaled` | wall-clock time multiplied by a factor *k* > 1 that the runner chooses (for example 10): every timer fires after 1/*k* of its duration. The runner sets `TESTKIT_TIME_SCALE` to 1/*k*, so testkit durations shrink by the same factor (TK-2). | SHOULD |
| `virtual` | a simulated clock that jumps to the next timer deadline whenever the run waits only for timers: no leaf, probe or service is running. While a process runs, it advances like `real`. | MAY |

- **CF-39.** `clock` on a case lists the modes it is valid in; the default is `[real, scaled]`. `virtual` is opted into by cases whose waits don't involve processes (`sleep`, `every` and `backoff` delays between attempts of a `fail` or `assert`), which then run in no time. The runner uses the fastest mode that both the case and the adapter support, unless told otherwise; a case valid in no supported mode is skipped (`requirement: clock`).
- **CF-40.** In `scaled` mode the adapter reports durations in plan time (measured time multiplied by *k*), so case bounds don't depend on *k*. Runners SHOULD NOT use *k* above 20: process start-up and pipe latency don't scale.
- **CF-41.** `jitter` (reference.md §5.3) draws from a seedable RNG. The runner passes a seed when the adapter supports one; cases with `jitter` assert bounds only, never the drawn values.

### 5.2 Tolerances

- **CF-42.** A `$min` bound is checked against the measured value plus a slack of 50ms (runners MAY raise it): limits never fire early, but measurement points differ between implementations.
- **CF-43.** A `$max` bound is multiplied by the runner's **timing factor** (default 1; slow CI MAY raise it). Case authors set `$max` generously: at least twice the expected value or the expected value plus 2s, whichever is larger.
- **CF-44.** Case durations stay short: a case's expected run time in plan time SHOULD be under 15s, and every case has a harness deadline of 60s plan time multiplied by the timing factor, after which the runner stops the run and reports a fail.

## 6. Pairwise policy

Most modifiers can be combined on one node, and their order is fixed (EM-4). Testing every combination would explode; testing none would miss order bugs. The policy:

- **CF-45.** **Validity matrix and sibling table.** Every cell of the validity matrix ([reference.md §7](../spec/reference.md#7-validity-matrix)) and of the repetition sibling table ([reference.md §5.2](../spec/reference.md#52-sibling-fields)) has a validation case: a minimal valid plan for each ✓ and a plan error for each "—". These cases MAY be generated by a script; generated cases are committed like any other and say so in `notes`.
- **CF-46.** **Modifier order, pairwise.** For every pair of modifier layers in EM-4 that may share a node, at least one run case puts both on one node and observes their relative order (which runs first, which sees the other's effect). Pairs are covered with as few cases as possible: one case MAY cover several pairs, chosen with any pairwise (2-way) generator over the layers, provided each case still cites the rules it tests. Cases for this policy live in `cases/combinations/`.
- **CF-47.** **Always explicit.** These combinations get their own cases, beyond pairwise coverage, because a spec rule names them:
  - `when` with every other layer: nothing applies to a skipped node (EM-5, EM-47);
  - `timeout` with `finally`, `lock`, `services` and repetition: what the timer covers and what it doesn't (EM-6, EM-7, EM-60, EM-62);
  - `timeout` or `attempt_timeout` around a node with `ignore_errors`, and an external stop: never hidden (EM-36);
  - `retry` with `attempt_timeout`, with captures, and with `BK_TIMEOUT_TOTAL` (reference.md §5.5, VA-32, EM-53);
  - `finally` with a failing body, a failing `finally`, and both (EM-51), and `finally` after `timeout` and cancellation (EM-7, EM-31);
  - `tempdir` with `cwd` and with repetition (once per node);
  - `services` with `finally` and with a failing service (EM-63 to EM-65);
  - `fail_fast` on `do`, `all` and `for`, and `any`/`race` with captures (EM-49, EM-59, VA-30);
  - `any` and `race` with children skipped by `when`: they don't take part, and an ordered `any` moves on (EM-45, EM-58);
  - a failed group at several nesting depths carrying its child's error unchanged, seen by `retry:` conditions and `result: error` (EM-66);
  - `lock` nested in `lock` (plan error) and `lock` with `timeout` (EM-60).
- **CF-48.** Triples and larger combinations get a case only when a rule names them or a pairwise case found a bug.

## 7. Rule citations and coverage

- **CF-49.** `rules` lists the IDs of the rules a case **tests**, not every rule it touches: a case that runs an `exec` doesn't cite SH-1 unless it checks argv. IDs use the spec's prefixes: `EM`, `RS`, `ER`, `VA`, `CO`, `SH`, `CP`, `RF` (the static rules of reference.md §8).
- **CF-50.** Normative text without rule IDs (currently syntax.md; rule IDs for it are pending, tracker F-0010) is cited in `spec` (`syntax.md§3.1`, `syntax.md§6.5`). Plan-error cases also assert `detail.rule` (CF-24).
- **CF-51.** **Coverage** is the share of rule IDs in `spec/*.md` that at least one case cites. Every rule ID SHOULD be cited by at least one case before `1.0.0`; execution-model.md §10 requires it for every `EM-n`. A rule that can't be tested through the run result (for example a recommendation to implementations) is listed below with the reason, and counts as covered.
- **CF-52.** A coverage report lists, per spec file, the uncovered rule IDs and, per rule, the cases that cite it. It is computed from the case files alone.

**Rules without cases:** none yet; the list is filled in as cases are written.

## 8. Runner contract

A **runner** reads the cases, prepares each one, runs it through the adapter and reports the outcome. Each implementation provides its runner and adapter (for blokky-cli in its repository, against a pinned checkout of this suite).

### 8.1 What the adapter provides

- **CF-53.** **Run a plan:** given the plan bytes, the ordered inputs, an environment, a working directory and a clock mode, run the plan as a user of the implementation would, and return either the plan and input errors or the result document (§3.6).
- **CF-54.** **Declare support:** the supported feature ids (CF-12), clock modes (§5.1), the RNG seed (CF-41) and whether it can stop a run from outside (CF-22).
- **CF-55.** **Stop a run** from outside on request, when the implementation supports external stops.

### 8.2 What the runner provides

- **CF-56.** **A fresh work directory** per case, empty except for `files`, used as the run's cwd. Nothing in it is shared between cases.
- **CF-57.** **The base environment:** `PATH` with the directory holding the testkit and the case's aliases first, then the directories the OS's shells need; the variables the OS needs to run processes (`HOME`, `TMPDIR`; on Windows `SystemRoot`, `PATHEXT`, `COMSPEC`, `USERPROFILE`, `TEMP`, `TMP`); `TESTKIT_LOG` (TK-5) and `TESTKIT_TIME_SCALE` (TK-2); then the case's `env`. Nothing else is inherited from the runner's own environment, so `from_env` and `env:` cases are deterministic.
- **CF-58.** **The testkit** ([testkit-interface.md](testkit-interface.md)) as `blokky-testkit` on `PATH`, and an alias for each entry of `programs` (TK-6).
- **CF-59.** **Isolation:** cases MAY run in parallel, except cases that share a port (CF-14). Lock names are unique per case (CF-14), so parallel cases don't contend.

### 8.3 Checking

- **CF-60.** The runner applies the platform overrides (§4), checks requirements and features (§3.2), picks the clock mode (§5.1), prepares the work directory, runs the plan, then matches the outcome against `expect` (§3.7), including the invocation log and the files.
- **CF-61.** For a validation outcome, the runner also checks that the invocation log is empty (CF-23); for a run outcome, that the run produced a result document (EM-3).

### 8.4 Reporting

- **CF-62.** Each case ends with one outcome:

| Outcome | When |
|---|---|
| `pass` | Every expectation matched. |
| `fail` | A mismatch (with the first mismatch, CF-32), a missing result, the harness deadline (CF-44), or a failed not-supported check (CF-12). |
| `skip` | With a reason: `not supported: <feature>`, `requirement: <key>`, or `platform: <reason>`. |
| `error` | The case itself is broken (unknown key, invalid YAML, a matcher misuse) or the runner failed. |

- **CF-63.** A runner reports, in a machine-readable form of its choice (for example JUnit XML or JSON lines), every case's id, outcome, reason and cited rules, plus totals and the **pass rate**: passes divided by all cases that weren't skipped for `requirement` or `platform`. Cases skipped as not supported count as not passed, so the pass rate measures how much of the language an implementation covers.
