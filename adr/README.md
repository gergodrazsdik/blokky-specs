# Architecture decision records (blokky-specs)

Decisions about the language: syntax, semantics, contracts and schemas. Implementation and process decisions live in [blokky-cli/docs/adr](https://github.com/gergodrazsdik/blokky-cli/tree/main/docs/adr).

ADRs are **grouped**: a baseline ADR, then one ADR per batch of answered open questions (brief §4, §8 step 2), rather than one file per tiny decision. Answers keep the brief's question IDs.

## Index

| ADR | Title | Status | Questions |
|---|---|---|---|
| — | *(none yet)* | | |

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
