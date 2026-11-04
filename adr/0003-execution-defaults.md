# 0003: Execution and defaults (open-question batch 2)

- Status: accepted
- Date: 2026-11-04
- Questions: Q4, Q5, Q7, Q8, Q-k, Q-r

## Context and problem statement

The [specification-phase brief](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/design/brief.md) §4 lists questions that must be answered before the language spec draft is written. This ADR records the maintainer's answers to batch 2, execution and defaults: shells and their invocation, duration defaults and grace accounting, output and capture limits, `max_items`, and concurrency. It refines [ADR 0001](0001-language-baseline.md) and builds on [ADR 0002](0002-language-core.md).

Each question was asked as a multiple choice with a recommendation, on 2026-11-04. The options considered are listed per decision below; the chosen one is marked.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| Q4a v0.1 shells | **bash, sh, pwsh, powershell**; move powershell 5.1 to later; add zsh |
| Q4b detection | **bash → sh on Unix, pwsh → powershell on Windows**; Windows pwsh only; no detection |
| Q4c bash/sh | **bash `pipefail` only, no `-e`**; no prologue; `-euo pipefail` / `-eu` |
| Q4d Git Bash | **explicit config path only**; PATH minus the WSL launcher; unsupported on Windows |
| Q4e pwsh/powershell | **`$ErrorActionPreference = 'Stop'` only**; also stop on native exit codes; no prologue |
| Q5a global `timeout` | **none, the run budget bounds the run**; implicit root `timeout` |
| Q5b `leaf_timeout` | **none**; 10m; 30m |
| Q5c `finally_timeout` | **5m**; 1m; none |
| Q5d grace / `drain_timeout` / `cleanup_reserve` | **5s / 2s / 30s**; 10s / 5s / 60s; 2s / 1s / 15s |
| Q-k grace vs `timeout` | **not counted: TERM when `timeout` fires**; counted: TERM at `timeout` − grace |
| Q-r concurrency | **defaults as today, cap 16, clamp and warn**; cap = CPU count; no cap; cap 16, error above it |
| Q-r `any` errors | **built-in code with every cause**; last child's error; first child's error |
| Q7a report | **tails 50 lines ≤ 4 KiB, report 32 KiB**; 20 lines ≤ 2 KiB, 16 KiB; 200 lines ≤ 16 KiB, 128 KiB |
| Q7b logs | **100 MiB per leaf, 1 GiB per run**; 16 MiB / 256 MiB; unlimited |
| Q7c `max_capture_bytes` | **1 MiB**; 64 KiB; 16 MiB |
| Q8 `max_items` | required, no default; **optional, default 1000**; optional, default 100 |

## Decision outcome

All answers follow the recommendation except Q8, where the maintainer chose an optional `max_items` with a default of 1000 over making it required.

### Q4: shells

**v0.1 set confirmed:** `bash`, `sh`, `pwsh`, `powershell` (Windows PowerShell 5.1). `zsh` and `fish` are `later`; `cmd` stays unsupported.

**Detection confirmed:** when neither the leaf's `shell:`, `defaults.shell` nor config names a shell, Blokky picks `bash`, else `sh` on Unix (never `$SHELL`), and `pwsh`, else `powershell` on Windows. `blokky plan` shows the resolved shell and binary.

**Invocation and error handling** (normative runner table in `spec/shells.md`):

| Shell | Invocation | Error handling |
|---|---|---|
| `bash` | `bash --noprofile --norc -o pipefail <file>` | `pipefail` on; no `-e`, no `-u` |
| `sh` | `sh <file>` | none |
| `pwsh` | `pwsh -NoProfile -NonInteractive -File <file>.ps1` | `$ErrorActionPreference = 'Stop'` |
| `powershell` | `powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <file>.ps1` (file written with a UTF-8 BOM) | `$ErrorActionPreference = 'Stop'` |

- `sh` gets no options: dash, the usual `/bin/sh`, rejects `--noprofile`/`--norc`, and a non-interactive `sh` reads no startup file once `ENV` is cleared (as it always is). This corrects the brief's "bash/sh: `--noprofile --norc`".
- `pipefail` is set with the `-o pipefail` option, not a prepended line, so line numbers in shell error messages match the plan. A failing command in the middle of a bash or sh script doesn't stop it; the script's exit status is the leaf's.
- In PowerShell, a cmdlet error ends the script with exit code 1 instead of being written to stderr while the script exits 0. `$PSNativeCommandUseErrorActionPreference` stays off, so a failing native program doesn't stop the script, matching "no `-e`" in bash.
- Every prologue and option is shown in `leaves` and `blokky plan`.

**Git Bash and MSYS on Windows:** `bash` and `sh` resolve only through a config key that gives the absolute path to the binary. There is no PATH lookup on Windows, because one can find `C:\Windows\System32\bash.exe`, the WSL launcher. A reached `bash`/`sh` script on Windows without that key is an error that names the key.

### Q5: duration defaults

| Setting | Default | Notes |
|---|---|---|
| Plan or group `timeout` | none | The run budget (default: Q-f) is the only implicit limit on the run. |
| `leaf_timeout` | none | `defaults.leaf_timeout` and a config key can set one. Hung commands are caught by the run budget. |
| `finally_timeout` | 5m | Per node. In cancel, budget or shutdown mode it is clamped by the cleanup deadline. |
| grace (TERM or CTRL_BREAK → KILL) | 5s | Also bounds the confirmation of cancelled siblings in joins (plus a fixed reap timeout). |
| `drain_timeout` | 2s | How long pipes are read after the leaf's direct child exits. |
| `cleanup_reserve` | 30s | The single cleanup deadline for budget, cancel and shutdown mode. |
| report slice | 2s | Fixed, not configurable: the final part of the cleanup deadline, kept for writing the report. |

All configurable values above are free config keys (key names in the config docs, Q11). A probe's limit is its own `timeout:`, else the smaller of `probe_timeout` (30s, ADR 0002) and `leaf_timeout` when one is set.

### Q-k: grace and `timeout`

The grace period does **not** count against `timeout`. When `timeout` or `attempt_timeout` fires, Blokky sends TERM (Windows: CTRL_BREAK where a console is attached) and KILL a grace period later, like coreutils `timeout -k`. A node can therefore end up to grace plus the reap timeout after its limit; the report shows the real duration. A `timeout` shorter than the grace period needs no special rule. `finally` still runs afterwards under `finally_timeout` (ADR 0002, Q1).

### Q-r: concurrency and `any` errors

**Defaults unchanged:** `all` starts every child, `any` runs one at a time (an ordered fallback), and `for` runs iterations one at a time unless `concurrency` is set.

**Cap:** a free config key `max_concurrency` (default 16) caps the effective concurrency of every `all`, `any` and `for` node. A literal `concurrency` above the cap is clamped, with a lint warning; `blokky plan` shows the effective value. A plan therefore never fails because of someone else's config. The cap applies per node, not to the run's total number of leaves: a `for` with 16 slots whose body is an `all` of 16 children can run 256 leaves.

**`any` when every child fails:** the node fails with a built-in code (named in `spec/errors.md`). Every child's error is attached as a cause, in plan order, and the message gives the count. `retry` and `result:` conditions can match the built-in code.

### Q7: output and capture limits

| Limit | Default | Behaviour when exceeded |
|---|---|---|
| Report tail per leaf stream | last 50 lines, at most 4 KiB | The tail keeps the end; it is cut at a UTF-8 character boundary. |
| stdout report | 32 KiB | Deterministic truncation: collapse succeeded subtrees, aggregate loop iterations, shrink tails. The full report stays in `report.json`. |
| `max_log_bytes` per leaf | 100 MiB | Logging stops with a truncation marker; the leaf keeps running and its pipes are still drained into the tail buffers. |
| Logs per run | 1 GiB | The same, for every leaf still running. |
| `max_capture_bytes` | 1 MiB | `capture` fails with an error that suggests `capture_file`; values are never truncated. |

All are free config keys; `max_log_bytes` is also a leaf field. Separately, mapping a value into a leaf's environment beyond the OS limit (about 128 KiB per string on Linux, 32K characters on Windows) fails at spawn with its own error that names the variable.

### Q8: `max_items`

For `for` over captured output (`items`, `lines`; both `later`), `max_items` is **optional with a default of 1000**. More items than `max_items` fails the node before the first iteration; items are never truncated. `blokky plan` shows the effective value. This replaces the brief's "mandatory `max_items`".

### Consequences

- Good: the draft spec can fill in `shells.md`, the timeline in `execution-model.md` and the limits in `output-contract.md` without placeholders.
- Good: `sh` runs as plain `sh <file>`, so dash, busybox and other minimal shells work.
- Good: no hidden per-leaf or per-group time limit can fail a long build; the run budget is the single backstop.
- Neutral: limits overrun by up to grace plus the reap timeout; the cancellation timeline and conformance cases must show it.
- Neutral: the concurrency cap is per node. A run-wide limit on running leaves could come later if fan-out turns out to be a problem.
- Bad: the PowerShell prologue is a line in the script file, unlike bash's `-o pipefail`. `using` statements, `param()` and `#Requires` must come first in a script, so `shells.md` has to define where the prologue goes (or how it is applied) without breaking them or shifting line numbers.
- Bad: with an implicit `max_items`, a plan's bound isn't visible in its text; reviewers rely on `blokky plan`.

## More information

- Brief: §3.1 (`all`/`any`/`for`, timeouts), §3.2 (report, leaf output, run budget), §3.5 (shells), §3.8 (lifecycle, cleanup deadline), §4 (questions).
- Tracker: T-0009; the answers are linked from the [open-questions table](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/plan/TRACKER.md#open-questions).
- Spec files that apply these answers: `spec/shells.md` (Q4), `spec/execution-model.md` (Q5, Q-k, Q-r), `spec/output-contract.md` (Q7), `spec/variables.md` (Q7c, Q8), `spec/errors.md` (the `any` code).
- Related open questions: Q-f (default run budget), Q11 (config key names and trust classes, including the Git Bash path key).
