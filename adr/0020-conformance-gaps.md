# 0020: Gaps found by the first conformance cases

- Status: accepted
- Date: 2026-11-07
- Questions: none from the brief; raised while checking the first conformance cases (tracker F-0015)

## Context and problem statement

The first conformance cases ([PR #42](https://github.com/gergodrazsdik/blokky-specs/pull/42)) were checked against the spec text by a second agent. Three expectations turned out not to be determined by the spec, so the cases left them out:

1. SY-1 gives a plan error the position of the offending key, but an error about a **missing** key (an `until` without `max` or `timeout`, RF-5; an `if` without `then`) has no offending key.
2. `BK_INPUT_UNKNOWN`'s `detail.suggestion` had no closeness rule (only `branch` → `BRANCH` as an example), and nothing said it must be present.
3. EM-15 gave Windows leaves a console only as a SHOULD, so whether a timed-out Windows leaf gets the graceful stop and the grace period (EM-26) was implementation-defined.

## Considered options

| Item | Options (chosen in bold) |
|---|---|
| Position of a missing-key error | **the key that requires it** (`until`, `if`), else the mapping; the node's first key; no position |
| Closeness of suggestions | **edit distance ≤ 2 after case mapping, as for unknown keys, required when one exists**; case-only matches; optional field |
| Console for Windows leaves | **MUST**; keep SHOULD and let cases accept both; decide after the spikes |

## Decision outcome

- **SY-1.** A missing-key error points at the key that requires the missing one (`until` for RF-5, `if` for a missing `then`); when no key requires it, at the mapping that lacks it.
- **SY-30.** "Closest" is defined: the smallest Levenshtein distance between the names after simple uppercase mapping (CO-12), at most 2, ties to the name listed first. `detail.suggestion` MUST be present when a close name or synonym exists. The same rule applies to unknown inputs (variables.md §4.3, errors.md).
- **EM-15, EM-26.** Every Windows leaf MUST have a console the graceful stop can reach (its own hidden console, or its own process group on a shared hidden console). `graceful: none` remains only for a process that has left its console itself.

### Consequences

- Good: validation cases assert positions and suggestions; timing cases need no Windows branch for the grace period.
- Good: agents get a suggestion for a typo in an input name, not only for a case mistake.
- Neutral: the Windows process-control spike must confirm that a hidden console per leaf works with Job Objects (spike plan).

## More information

- Applied in: `spec/syntax.md`, `spec/variables.md`, `spec/errors.md`, `spec/execution-model.md`, `spec/results.md`, `conformance/README.md`, `conformance/cases/`.
- Tracker: T-0060; finding F-0015.
