# 0010: Short budgets and variable details (draft round 4)

- Status: accepted
- Date: 2026-11-05
- Questions: tracker finding F-0006; three details raised while drafting `spec/variables.md` (T-0018)

## Context and problem statement

Drafting `spec/execution-model.md` left one case open (F-0006): what happens when the run budget is at or below `cleanup_reserve` (default 30s), for example `--max-duration 20s`. Drafting `spec/variables.md` raised three details the brief and earlier ADRs don't fix: the value of a JSON `null` in captures and conditions, the minimum length for secret masking ("values shorter than a minimum length are not masked", brief §3.1), and what a capture does with output that isn't valid in the leaf's encoding.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| F-0006 budget ≤ `cleanup_reserve` | usage error; shrink the reserve proportionally; **run with no reserve** |
| JSON `null` | **empty string**; the text `null`; undefined |
| Masking minimum length | 4; **6**; 8 characters |
| Undecodable captured output | **error**; replace with U+FFFD |

## Decision outcome

All answers follow the recommendation, except F-0006, which was asked as an open item without one; the maintainer chose to run with no reserve.

- **Short budgets** (EM-54): if the budget is at or below `cleanup_reserve`, the effective reserve is zero. Budget mode starts at the budget minus the 2s report slice; grace periods and `finally` get no time, processes are force-killed, and the run ends at its budget. Blokky warns at run start.
- **JSON `null`** becomes `''` in field captures and `json:` condition paths, so `{ var: X, empty: true }` tests for it. A missing key stays an error.
- **Masking** applies to secret values of at least 6 characters; shorter secrets aren't masked, and Blokky warns, naming the reference, not the value.
- **Undecodable output** fails a `capture` with a distinct code that suggests `encoding:` or `capture_file`; captured values are never silently altered. Tails and logs are unaffected.

### Consequences

- Good: a short budget never fails the run up front; the caller's limit is always honoured.
- Bad: with a short budget, `finally` cleanup doesn't run when the budget is hit; artefacts are still registered, so `clean`/`gc` can remove them.
- Neutral: `''` and JSON `null` are indistinguishable in a variable.
- Neutral: short secrets (PINs) are only warned about.

## More information

- Applied in: `spec/execution-model.md` EM-54; `spec/variables.md` VA-21, VA-23, VA-51, VA-52.
- Tracker: F-0006, T-0018.

Note (2026-11-07): EM-54 moved to blokky-cli with the run-budget rules; its ID isn't reused in the spec.
