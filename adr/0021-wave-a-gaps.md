# 0021: Gaps found by the wave A conformance cases

- Status: accepted
- Date: 2026-11-07
- Questions: none from the brief; raised while writing and checking the wave A validation cases (tracker T-0061, F-0016; [review notes](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/review/conformance-wave-a.md))

## Context and problem statement

Five agents wrote the wave A validation cases, and five more read every case against the spec. Wrong cases were fixed. What remained were places where the spec doesn't decide an outcome, so a case can't assert it: which rule ID a plan error reports, which code a mistake gets, error positions, and a number of smaller details. The maintainer decided D-1 to D-4 and accepted the batch B-1 to B-10 on 2026-11-07.

## Considered options

| Item | Options (chosen in bold) |
|---|---|
| D-1 one mistake, several rule IDs | **the reference.md §8 rule is canonical, with a precedence for §8 overlaps**; merge the restatements; cases accept any ID |
| D-2 which code | **unknown key / key in the wrong place or a relation / a value alone**; codes shaped by what a schema reports |
| D-3 leaf loop bounded only by `timeout` | **withdrawn**: the premise was a misreading (below) |
| D-4 `return` with no enclosing sequence | **a plan error under RF-29**; the root always counts as a sequence |
| B-1 to B-10 | **accepted as a batch** |

## Decision outcome

- **D-1.** A plan error reports one rule. The [reference.md §8](../spec/reference.md#8-rules-beyond-the-schema) rule is canonical: a rule elsewhere that restates it is reported under its `RF-n` ID (syntax.md SY-3, variables.md intro, errors.md §4). Overlaps inside §8 go to the more specific rule:
  - RF-4, RF-12, RF-28, RF-30, RF-31 and RF-32 win over RF-3;
  - RF-7 wins over RF-26 when an input or an enclosing scope is involved;
  - RF-9 wins over RF-27 for `${…}` in a literal field;
  - RF-27 wins over RF-23 for a template outside `set` and `vars`.
- **D-2.** Each code has a defined scope (errors.md §4):
  - `BK_PLAN_UNKNOWN_KEY`: a key that no kind accepts in that kind of mapping.
  - `BK_PLAN_INVALID`: a language key in the wrong place, and every rule relating keys, values or scopes.
  - `BK_PLAN_VALUE`: anything one value decides alone (grammar, type, empty value or list, a regex outside the subset, reserved prefixes).

  Both INVALID and VALUE carry `detail.rule`, and RF-21 and RF-22 are VALUE.
- **D-3, withdrawn.** The gap read reference.md §4.3 as making a leaf's own `timeout` per-iteration under `while`/`until`. ADR 0018 (S-9) made only `defaults.leaf_timeout` per-attempt; a node's own `timeout` always limits the whole node. §4.3's "it" was ambiguous, and it now names `defaults.leaf_timeout`. RF-5 is unchanged.
- **D-4.** RF-29 now requires a `return` to have an enclosing sequence, which must not be reached through `all`, `any` or `race`. A root `return`, or one under a root `if` or `all`, is a plan error.
- **B-1 Positions (SY-1).**
  - Lines end at LF, CRLF or a lone CR. Columns are 1-based code points, and a BOM isn't counted.
  - A quoted scalar is located at its opening quote, and an error inside a string at the value's start.
  - A missing value is located at its key. When two keys conflict, the later one is reported.
  - Whole-text errors are at 1:1; the depth error is at the first node that is too deep.
- **B-2 Invalid text.**
  - Invalid UTF-8 is one error, at the first bad byte, with `detail.offset` (SY-7).
  - A UTF-16/32 BOM is the only error reported for that text (SY-6).
  - Character-lint errors end processing before YAML parsing (SY-10).
  - `detail.codepoint` is written `U+XXXX`.
- **B-3 Details.**
  - `BK_PLAN_VERSION` always carries `detail.supported`.
  - For a multi-part synonym, `detail.suggestion` is the key it names. SY-30's candidates are the keys valid in that mapping, in the schema's `properties` order.
  - A targeted error (SY-91) replaces the generic one.
- **B-4 Warnings** stay unobservable in 1.0, and SY-8 is exempt from coverage.
- **B-5 Grammars.**
  - A duration of zero is only `0s`, but zero parts inside a non-zero duration are allowed (SY-58).
  - An unescaped `{` or `}` in a glob is a plan error (SY-73).
  - `$${` means `${` in every field (SY-84).
  - An escape of a character outside the listed ones is outside the regex subset (SY-61).
  - A JSON-path index has no leading zeros (SY-67).
  - Escaped characters are shown as `\uXXXX` (SY-98).
- **B-6 Names and inputs.**
  - Reserved prefixes are `BK_PLAN_VALUE`.
  - A literal marked secret is RF-19.
  - An `--input` name that breaks the name grammar is `BK_INPUT_SYNTAX`; a well-formed undeclared name is `BK_INPUT_UNKNOWN`.
  - An unset `from_env` in `vars` is reported with the plan errors, at its entry (VA-40).
  - The 4 KiB and 32 KiB input limits are normative (VA-14).
- **B-7 Masking** follows the value: a non-secret output whose value contains a secret value is masked (VA-47).
- **B-8 Binding.**
  - RF-6 lists `index` and `carry`, and RF-7 covers shadowing by them.
  - Sequential loops may reuse a loop variable (RF-26).
  - RF-8 ignores names scoped to a loop iteration.
- **B-9 Editorial and schema.**
  - The §5.8 `collect` example is the right way round.
  - The §4 modifier table lists `return` with the no-process kinds.
  - §2.6 allows `concurrency` and `fail_fast` on `race` inside `for:`.
  - §2.10 says "an enclosing `retry`".
  - The SY-89 `[ -f x ]` row is corrected.
  - The schema rejects `attempt_timeout` on the no-process kinds.
  - §7 notes that `log` × `collect` can't be used.
- **B-10 Conformance format.**
  - `inputs` is a run-outcome key.
  - Checker fixes: a string `exec` is only `exec-string`, a service's array `exec` counts as `exec`, a root that isn't a mapping skips the feature check, and a matcher in `detail.rule` no longer crashes it.
  - typos ignores `plan_base64`.
  - Eleven rules join the exemptions.

### Consequences

- Good: every plan error in the cases has one code, one rule and a position, so a validator either passes or fails them clearly.
- Good: agents get one rule ID per mistake, pointing at the §8 summary of the language's static rules.
- Neutral: the VA, SY and CO restatements stay as explanations next to their topic; their IDs are cited by cases only where they add behaviour beyond the RF rule.

## More information

- Applied in: `spec/syntax.md`, `spec/reference.md`, `spec/variables.md`, `spec/errors.md`, `schema/blokky.schema.json`, `conformance/README.md`, `conformance/case.schema.json`, `scripts/check.py`, `_typos.toml`.
- Tracker: T-0061; finding F-0016.
