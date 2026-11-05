# Architecture decision records (blokky-specs)

Decisions about the language: syntax, semantics, contracts and schemas. Implementation and process decisions live in [blokky-cli/docs/adr](https://github.com/gergodrazsdik/blokky-cli/tree/main/docs/adr).

ADRs are **grouped**: a baseline ADR, then one ADR per batch of answered open questions (brief §4, §8 step 2), rather than one file per tiny decision. Answers keep the brief's question IDs.

## Index

| ADR | Title | Status | Questions |
|---|---|---|---|
| [0001](0001-language-baseline.md) | Language baseline | accepted | Q14, Q-p |
| [0002](0002-language-core.md) | Language core (open-question batch 1) | accepted | Q1, Q2, Q3, Q12, Q13, Q-m, Q-n, Q-s |
| [0003](0003-execution-defaults.md) | Execution and defaults (open-question batch 2) | accepted | Q4, Q5, Q7, Q8, Q-k, Q-r |
| [0004](0004-validator-and-inputs.md) | Validator protocol and input scope (open-question batch 4) | accepted | Q9, Q-in1, Q-in3, Q-in4, Q-in5 |
| [0005](0005-containers-become-locks.md) | Containers, `become` and locks (open-question batch 5) | accepted | Q16, Q17, Q-j |
| [0006](0006-shims-and-license.md) | `.cmd` shims and the spec license (open-question batch 6) | accepted | Q-l, Q-q (license, testkit) |
| [0007](0007-syntax-details.md) | Syntax details (draft round 1) | accepted | — (raised in T-0015) |
| [0008](0008-repetition-details.md) | Repetition details (draft round 2) | accepted | — (brief §3.1 D15, raised in T-0016) |
| [0009](0009-status-propagation.md) | Status propagation and joins (draft round 3) | accepted | — (brief §3.8 D15, raised in T-0017) |
| [0010](0010-variables-details.md) | Short budgets and variable details (draft round 4) | accepted | — (F-0006, raised in T-0018) |
| [0011](0011-pwsh-prologue.md) | PowerShell prologue placement (draft round 5) | accepted | — (left open by 0003, raised in T-0020) |
| [0012](0012-container-details.md) | Container mount path on Windows and default user (draft round 6) | accepted | — (left open by 0005, raised in T-0021) |
| [0013](0013-scope-and-versioning.md) | Language-only scope and 1.0 draft versioning | accepted | — (direction revision; supersedes parts of 0001, 0002) |
| [0014](0014-remaining-features.md) | Remaining language features (batch 7) | accepted | Q18; `race`, `lock`, `services`, `for` sources, `collect`, `zsh`/`fish` |

## Format

Files are named `NNNN-short-title.md` (four digits, never reused) and follow a [MADR](https://adr.github.io/madr/)-style template:

```markdown
# NNNN: Title

- Status: proposed | accepted | superseded by NNNN | deprecated
- Date: YYYY-MM-DD
- Questions: Q3, Q-m (brief §4 IDs this ADR answers)

## Context and problem statement
## Considered options
## Decision outcome
Chosen option: "…", because …
### Consequences
## More information
```

Everything can still change until v1.0.0: a later ADR supersedes an earlier one instead of editing it.
