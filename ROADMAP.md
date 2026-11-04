# Roadmap: Blokky language

This is the high-level picture of the language. Task-level detail lives in the [work tracker](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/plan/TRACKER.md); implementation and distribution are in the [blokky-cli roadmap](https://github.com/gergodrazsdik/blokky-cli/blob/main/ROADMAP.md).

The draft spec describes **every** planned feature, tagged `v0.1` or `later`. Value shapes are fixed now, even for later features, and later keywords are reserved: a v0.1 parser rejects them with a clear "not supported in this version" error.

## Phases

1. **Spec draft:** the complete language, all milestones. *(current)*
2. **Spikes:** verify the runtime behaviour the spec depends on (blokky-cli).
3. **Finalized spec:** spike findings folded in; spec version 0.1.
4. **v0.1 implementation**, then the MCP host, then signing and packaging (blokky-cli).

## v0.1

- **Leaves:** `exec` (argv, no shell) and `script` (shell text run from a file).
- **Shells:** `bash`, `sh`, `pwsh`, `powershell` (Windows PowerShell 5.1). `cmd` is not supported.
- **Structure:** `do` (sequence), `all` (parallel), `any` (first success), `if`/`then`/`else`.
- **Simple nodes:** `sleep`, `log`, `fail`, `assert`.
- **Modifiers:** `name`, `when`, `timeout`, `tempdir`, `cwd`, `env`, `export`, `finally`, `ignore_errors`, `attempt_timeout`, `capture` / `capture_file`.
- **Repetition:** `retry`, `while`, `until`, and `for` over `each`, `count` and `glob`.
- **Conditions:** `var`, `env`, `path`, `host`, `result` and `probe` subjects; string, set, regex, emptiness, existence and numeric operators; `all`/`any`/`not`.
- **Plan document:** `blokky:` version, `inputs:` (string inputs with `in:`/`matches:` constraints), `outputs:`, `defaults:`.
- **Contracts:** the run report, event log, `leaves` output and validator protocol, each with its own `schema_version`.

## Later

- **`race`:** the first completion decides.
- **`for` sources:** `items` (JSON array from a captured variable), `lines`, `matrix`; `collect` for results.
- **`lock`:** named advisory locks.
- **`services`:** background processes with `ready:` conditions (`port`, `output` subjects).
- **`container`:** ephemeral and existing containers.
- **`become`** and `defaults.become`.
- **`consent`:** out-of-band OS consent (reserved keyword).
- **Shells:** `zsh` and `fish`.
- **Under consideration** (open questions): native nested plans (Q-in1), `--input-file` (Q-in3), env-sourced secret inputs (Q-in4), references in literal fields (Q-in5).
