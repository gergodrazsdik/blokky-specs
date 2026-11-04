# 0008: Repetition details (draft round 2)

- Status: accepted
- Date: 2026-11-04
- Questions: none from the brief's §4 list; the brief's §3.1 lists these as "must be specified in the reference" (D15). Raised while drafting `spec/reference.md` (T-0016).

## Context and problem statement

The brief leaves several repetition behaviours to the reference: the meaning of `every` and whether there is a wait before the first iteration, backoff and jitter, what `retry: true` retries, the status of a zero-iteration `while`, and the item value and index base of `for: { count }`. They were asked as multiple choices with a recommendation, on 2026-11-04.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| `every` meaning and default | **delay after the end, default 1s**; period from the start; delay after the end, default 0s |
| Backoff and jitter shape | `backoff: fixed \| exponential` with a cap; **mapping `backoff: { factor, max }`, fractional `jitter`**; no backoff in v0.1 |
| Backoff mapping rules | **factor 1–10, `max` default 5m, jitter in [1 − j, 1]**; `max` required; integer factor and percentage jitter |
| `retry: true` table and default `max` | **process failures only, `max` 3**; everything but cancellation; same table with `max` required |
| Zero-iteration `while` | **succeeded with 0 iterations**; skipped |
| `count` items and `_INDEX` | **0-based, item = index**; 1-based `count` items; 1-based everywhere |

## Decision outcome

All answers follow the recommendation except the backoff shape, where the maintainer chose the mapping form; its rules then follow the recommendation.

- **`every`:** the delay between the end of an attempt or iteration (including its condition check) and the start of the next. No wait before the first; default 1s for `retry`, `while` and `until`; `every: 0s` removes it. Waits respond to cancellation immediately.
- **Backoff** (`retry` only): `backoff: { factor: F, max: D }`; the delay before attempt n+1 is `every × F^(n−1)`, capped at `max`. `factor` is a decimal from 1 to 10 and required in the mapping; `max` defaults to 5m. Without `backoff`, the delay is a fixed `every`.
- **Jitter** (`retry` only): `jitter: J`, a decimal with 0 < J ≤ 1; each delay is multiplied by a random value in [1 − J, 1] from a seedable RNG.
- **`retry: true`** retries process failures (non-zero exit, signals), `BK_TIMEOUT_ATTEMPT` and capture failures. It doesn't retry `fail`/`assert` codes, condition errors or spawn errors; only a `retry:` condition that matches their code does. Total timeouts, cancellation, the run budget and shutdown are never retried. `max` defaults to 3 for `retry`.
- **Zero-iteration `while`:** `succeeded`, with `iterations.count: 0` and `ended_by: condition`; `finally` runs.
- **`count`:** items are `0` … `N−1`, equal to the 0-based `<AS>_INDEX`; every source's `_INDEX` is 0-based; `count: 0` runs zero iterations and succeeds.

Derived without a separate question:

- `attempt_timeout` covers the body only: not condition probes, not the `every` wait.
- After an attempt killed by `attempt_timeout`, a `retry:` condition is evaluated with `result: error` = `BK_TIMEOUT_ATTEMPT`. In `while`/`until` it is a body failure governed by `on_body_failure`, and no condition is checked for that iteration.

### Consequences

- Good: `spec/reference.md` §5 states every repetition behaviour without placeholders.
- Good: the 1s default `every` prevents accidental hot loops.
- Neutral: the mapping backoff adds two fields (`factor`, `max`) and a decimal grammar to `syntax.md`.
- Bad: `retry: true` doesn't retry spawn errors or `fail`/`assert`; plans that want that must name the codes in a `retry:` condition.

## More information

- Applied in: `spec/reference.md` §5; `spec/syntax.md` §6.4 (decimals) and §7.4 (`backoff.factor`, `backoff.max`, `jitter`).
- Tracker: T-0016.
