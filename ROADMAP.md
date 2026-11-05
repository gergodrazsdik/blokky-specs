# Roadmap: Blokky language

This is the high-level picture of the language. Task-level detail lives in the [work tracker](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/plan/TRACKER.md); which features each CLI release supports, and distribution, are in the [blokky-cli roadmap](https://github.com/gergodrazsdik/blokky-cli/blob/main/ROADMAP.md).

The spec describes the **whole language 1.0**, with every planned feature; it has no milestone tags ([ADR 0013](adr/0013-scope-and-versioning.md)). Implementations may support features step by step and reject the rest with `BK_PLAN_NOT_SUPPORTED`.

## Versions

1. **`1.0.0-draft.1`:** the complete language, every feature specified to the same depth. *(in progress)*
2. **Example suite** covering every feature, then a **review** by the maintainer and an agent council, which also asks whether each feature earns its place. Accepted changes produce further drafts (`1.0.0-draft.N`).
3. **Conformance suite** for the features that survive the review.
4. **Refinement during the runtime implementation:** decisions the runtime can't confirm are revised in further drafts.
5. **`1.0.0`** once the runtime has validated the draft.

## The language 1.0

- **Leaves:** `exec` (argv, no shell) and `script` (shell text run from a file).
- **Shells:** `bash`, `sh`, `pwsh`, `powershell` (Windows PowerShell 5.1), `zsh`, `fish`. `cmd` is not supported.
- **Structure:** `do` (sequence), `all` (parallel), `any` (first success), `race` (first completion), `if`/`then`/`else`.
- **Simple nodes:** `sleep`, `log`, `fail`, `assert`.
- **Modifiers:** `name`, `when`, `timeout`, `lock`, `tempdir`, `cwd`, `env`, `export`, `container`, `become`, `services`, `finally`, `ignore_errors`, `attempt_timeout`, `capture` / `capture_file`.
- **Repetition:** `retry`, `while`, `until`, and `for` over `each`, `count`, `glob`, `items`, `lines` and `matrix`; `collect` for results.
- **Conditions:** `var`, `env`, `path`, `host`, `result` and `probe` subjects (`port` and `output` for services); string, set, regex, emptiness, existence and numeric operators; `all`/`any`/`not`.
- **Plan document:** `blokky:` version, `inputs:` (string inputs with `in:`/`matches:` constraints), `outputs:`, `defaults:`.
- **Reserved:** `consent` (out-of-band OS consent), not yet specified.

Some of these are still sketched and are being specified to full depth for `1.0.0-draft.1` (`race`, `lock`, `services`, `items`/`lines`/`matrix`, `collect`, `consent`, `zsh`/`fish`).

## Candidates

Revisited after real use; no keyword reserved ([ADR 0004](adr/0004-validator-and-inputs.md)): input files (Q-in3), env-sourced secret inputs (Q-in4), references in literal fields such as `timeout: { var: T }` (Q-in5).

Not planned: a native nested-plan node (Q-in1); nested runs stay a leaf that runs the implementation again.
