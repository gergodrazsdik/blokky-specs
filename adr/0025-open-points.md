# 0025: Open points after the conformance waves

- Status: accepted
- Date: 2026-11-07
- Questions: none from the brief; the points left open after ADR 0021 and after waves C and D (tracker F-0017, F-0021). Supersedes the "SY-91 is reported over CO-4" sentence of [ADR 0023](0023-wave-c-gaps.md) K-1.

## Context and problem statement

The conformance waves A to D left a few points undecided, and the cases accept either answer (`$one_of`) or don't assert them: which rule ID a plan error reports when no `RF-n` rule applies, a few overlaps and codes [ADR 0021](0021-wave-a-gaps.md) D-1 doesn't name, several error positions, the run error when an external stop arrives during `finally`, whether `?` in a glob matches a leading dot, and how container cases name their image. The maintainer decided all points as proposed on 2026-11-07.

## Considered options

| Item | Options (chosen in bold) |
|---|---|
| P-1 the image of container cases | **one image, pinned by digest: busybox 1.37.0**; any image with `sh`, `sleep` and `kill`, chosen by the runner |
| P-2 a stop during `finally` after the body failed | **the root keeps the body's error (EM-51), the run is `stopped`, and the run's error is the root's error**; the root's error becomes `BK_CANCELLED` (EM-57) |
| P-3 rule IDs when no `RF-n` rule applies | **the grammar or structure rule of syntax.md; restatements are reported as it; a targeted error reports the generic rule it replaces**; the rule of the file the field belongs to; SY-91 for every targeted error |
| P-4 to P-8 | **accepted as proposed** |

## Decision outcome

- **P-1 Container cases.** Cases name one image, pinned by digest: `docker.io/library/busybox@sha256:a7dbc319b1438115a207e11930dc4bb3e643dcb3ec0bdd694bb36cd8fad289ec` (busybox 1.37.0, a multi-arch index, with `sh`, `sleep` and `kill`, CP-36). They list `requires: { container-engine: true }`; runners pull the image beforehand; without an engine or the image the case is skipped with `requirement: container-engine` (new CF-66).
- **P-2 A stop during `finally`.** When an external stop arrives after the body already failed (for example during `finally`), the root keeps the body's error (EM-51); the run's status is `stopped`, and the run's error is the root's error. The root's `BK_CANCELLED` ([ADR 0024](0024-wave-d-gaps.md) L-1) applies only when the stop interrupted unfinished work (EM-57, results.md §2).
- **P-3 Rule IDs.** When no `RF-n` rule applies, the grammar or structure rule of syntax.md is reported: SY-52 for names, SY-53 for booleans, SY-54 for integers, SY-56 and SY-57 for durations, SY-20 for empty values. Restatements elsewhere (VA-4, VA-6, ER-1, SY-24, SY-25, SY-41, SY-42, CO-8) are reported as that `SY-n` rule. A targeted error reports the generic rule it replaces: SY-91 decides the message, not the ID. So a string condition reports CO-4, not SY-91, which supersedes ADR 0023 K-1's "SY-91 is reported over CO-4" (SY-3, SY-91, CO-4, errors.md §4).
- **P-4 Overlaps.** RF-23 is reported only when no more specific rule applies: RF-6, RF-16 and RF-27 win over it (RF-23, errors.md §4).
- **P-5 Positions.** An error is located at the narrowest token that is wrong: a scope error at the variable name inside `{ var: X }`; a secret literal at its `secret` key; the depth error at the first key of the first node that is too deep; content after `...` at that content; an unset `from_env` in `vars` at the environment variable name; an `env`/`export` name conflict at the later of the two names; `for` without `as` at the `for` key (SY-1, VA-40).
- **P-6 Codes.** `timeout: { var: X }` is `BK_PLAN_INVALID` with RF-9; a regex that doesn't compile is `BK_PLAN_VALUE` with RF-22 (not compiling is outside the subset); a root that is a list is `BK_PLAN_VALUE` with SY-32; `secret:` on an input is `BK_PLAN_UNKNOWN_KEY` with the targeted message (SY-32, SY-48, RF-9, RF-22, errors.md §4).
- **P-7 Globs.** `?` never matches a leading dot either, unless the pattern segment starts with `.` (SY-100).
- **P-8 CO-46.** The rule stays. `command:` looking at the host under `container` is observable with a container engine, so CO-46 stays testable and isn't exempt; its warning can't be asserted (SY-8).

Details the decisions implied, settled when applying them: container cases may run the pinned image's own programs (CF-4, CF-17), and CP-5 and CP-37 are exempt because neither is observable from a case; a tempdir's name starts with its `prefix` (reference.md §4.5); a value of the wrong type for its field is reported as SY-88 (errors.md §4); a character class (`[…]`) can't match a leading dot either (SY-100, as shells do); `secret:` on an input, an unknown key, carries no `detail.rule` (SY-48, errors.md §4).

### Consequences

- Good: every plan error has one rule ID and one position the cases can assert without `$one_of`, and a stopped run keeps the error that actually caused its failure.
- Good: container cases are reproducible on every engine and architecture.
- Neutral: cases that assert SY-91, or an ID the new precedence no longer reports, need updating; the checker doesn't check the rule choice.

## More information

- Applied in: `spec/syntax.md`, `spec/errors.md`, `spec/execution-model.md`, `spec/results.md`, `spec/reference.md`, `spec/variables.md`, `spec/conditions.md`, `conformance/README.md`.
- Tracker: findings F-0017 and F-0021.
