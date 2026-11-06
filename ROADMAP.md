# Roadmap: Blokky language

This is the high-level picture of the language. Task-level detail lives in the [work tracker](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/plan/TRACKER.md); which features each CLI release supports, and distribution, are in the [blokky-cli roadmap](https://github.com/gergodrazsdik/blokky-cli/blob/main/ROADMAP.md).

The spec describes the **whole language 1.0**, with every planned feature; it has no milestone tags ([ADR 0013](adr/0013-scope-and-versioning.md)). Implementations may support features step by step and reject the rest with `BK_PLAN_NOT_SUPPORTED`.

## Versions

1. **`1.0.0-draft.1`:** the complete language, every feature specified to the same depth. *(tagged 2026-11-05)*
2. **`1.0.0-draft.2`:** `set` and `vars` ([ADR 0015](adr/0015-set-and-vars.md)). *(tagged 2026-11-06)*
3. **`1.0.0-draft.3`:** fixes found while writing the examples, and the `command` subject ([ADR 0016](adr/0016-fixes-from-examples.md)). *(tagged 2026-11-06)*
4. **Example suite** covering every feature *(done 2026-11-06: [examples](examples/README.md))*, then a **review** by the maintainer and an agent council, which also asks whether each feature earns its place *(done 2026-11-07)*. Accepted changes produce further drafts (`1.0.0-draft.N`).
5. **`1.0.0-draft.4`:** the review's decisions: features ([ADR 0017](adr/0017-review-features.md)), semantics and corrections. *(in progress)*
6. **Conformance suite** for the features that survive the review.
7. **Refinement during the runtime implementation:** decisions the runtime can't confirm are revised in further drafts.
8. **`1.0.0`** once the runtime has validated the draft.

## The language 1.0

- **Leaves:** `exec` (argv, no shell) and `script` (shell text run from a file).
- **Shells:** `bash`, `sh`, `pwsh`, `powershell` (Windows PowerShell 5.1), `zsh`. `cmd` and `fish` are not supported.
- **Structure:** `do` (sequence), `all` (parallel), `any` (first success), `race` (first completion), `if`/`then`/`else`.
- **Simple nodes:** `sleep`, `log`, `fail`, `assert`, `set`, `return` (end a sequence early).
- **Modifiers:** `name`, `when`, `timeout`, `lock`, `tempdir`, `cwd`, `env`, `export`, `container`, `services`, `finally`, `ignore_errors`, `attempt_timeout`, `capture` / `capture_file`.
- **Repetition:** `retry`, `while`, `until`, and `for` over `each`, `count`, `glob`, `items`, `lines` and `matrix`; `collect` for results, `carry` to pass a value to the next iteration (pagination), `index` for the attempt or iteration number.
- **Conditions:** `var`, `env`, `path`, `command`, `host`, `result` and `probe` subjects (`port` and `output` for services); string, set, regex, emptiness, existence and numeric operators; `all`/`any`/`not`.
- **Variables:** `set` (bind variables from literals, references or `${}` templates), single assignment.
- **Plan document:** `blokky:` version, `inputs:` (string inputs with `in:`/`matches:` constraints), `vars:` (plan constants), `outputs:`, `defaults:`.

## Candidates

Revisited after real use; no keyword reserved ([ADR 0004](adr/0004-validator-and-inputs.md), [ADR 0014](adr/0014-remaining-features.md)): input files (Q-in3), env-sourced secret inputs (Q-in4), references in literal fields such as `timeout: { var: T }` (Q-in5), `exclude`/`include` for `matrix`, shared (read) locks.

Not planned: a native nested-plan node (Q-in1), since nested runs stay a leaf that runs the implementation again; switching users within a plan (`become`, [ADR 0017](adr/0017-review-features.md)), since plans call `sudo -n` as in bash.
