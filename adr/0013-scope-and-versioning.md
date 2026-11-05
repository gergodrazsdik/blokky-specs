# 0013: Language-only scope and 1.0 draft versioning

- Status: accepted
- Date: 2026-11-05
- Supersedes: in [ADR 0001](0001-language-baseline.md), "Versioning and spec structure" (milestone tags, reserved later keywords) and "Contracts" (contract ownership); in [ADR 0002](0002-language-core.md), the example value `blokky: 0.1` (Q13's grammar stays)
- Companion: [blokky-cli ADR 0006](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/adr/0006-phase-order-and-incremental-cli.md) (phase order, incremental CLI)

## Context and problem statement

The maintainer narrowed blokky-specs to the language and changed how it is versioned: the spec is completed with all planned features as a `1.0` draft and refined during the runtime implementation, while the CLI implements it incrementally. This ADR records what stays in this repo, what moves to blokky-cli, and how versions and milestone tags change. The questions were asked as multiple choices with a recommendation, on 2026-11-05.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| Scope of blokky-specs | **what a plan means and can observe**; keep the JSON contracts too; strictest (syntax and construct meaning only) |
| Versioning | **`1.0.0-draft.N` pre-releases, plans write `blokky: 1.0`, no milestone tags**; core/extended tags; plans name the draft version |
| Conformance timing | **format and testkit interface with the examples, cases after the review** |

## Decision outcome

All answers follow the recommendation.

### What stays in blokky-specs

- Syntax, the reference, variables, conditions, shells (`exec` splitting, `script` semantics), containers and privilege (language level).
- Execution semantics as a plan can observe them: modifier order, start order, timeouts and grace, cancellation, status propagation, error precedence.
- The error codes a plan can observe (`result: error`, `retry` conditions, statuses): node errors, in `spec/errors.md`.
- A new **abstract run-result model** (`spec/results.md`): node statuses, errors, attempts and iterations, outputs; what conformance cases assert on, independent of any JSON format.
- The plan schema, the example suite and the conformance suite (cases, format, testkit interface).

### What moves to blokky-cli

- `spec/output-contract.md` and `spec/leaves-and-validation.md`, with `schema/report.schema.json`, `events.schema.json`, `leaves.schema.json` and `validator.schema.json`.
- CLI-only error codes (usage, input values, plan reporting, config, approval, run, cleanup) and every reference to exit codes.
- Runtime mechanics in the spec text: the run budget and cleanup reserve as configuration, the run dir and artefacts, config keys and trust classes, the hook, approval records, lint rules and severities, OS process-control mechanisms (sessions, Job Objects, the lifeline, signals). The spec keeps the observable rule and points to blokky-cli for the mechanism.

### Versioning

- Spec releases are semver pre-releases `1.0.0-draft.1`, `1.0.0-draft.2`, …, until `1.0.0`; the maintainer creates the tags.
- Plans write `blokky: 1.0`; the `MAJOR.MINOR` grammar of ADR 0002 (Q13) is unchanged.
- The spec drops the `v0.1`/`later` milestone tags: every feature belongs to 1.0. Reserving keywords of later features is no longer a spec concept; a CLI that doesn't support a feature rejects it with "not supported by this blokky version" (blokky-cli ADR 0006).

### Conformance

The case format and the testkit interface are written with the example suite; the cases are written after the review, for the features that survive it, each citing the rule IDs it tests.

### Consequences

- Good: the spec describes one language, without runtime detail or release planning mixed in.
- Good: conformance cases don't depend on a particular JSON report format.
- Bad: the merged draft needs a cleanup pass across most spec files; rule IDs in moved text (`OC-n`, `LV-n`) move with it to blokky-cli.

## More information

- Brief: §0.1, §1.5, §1.6, §5, §8 (revised in blokky-cli PR #25).
- Tracker: the scope cleanup and versioning milestone (M1.3).
