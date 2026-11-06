# 0018: Review decisions on semantics

- Status: accepted
- Date: 2026-11-07
- Questions: none from the brief; raised by the agent council's review of `1.0.0-draft.3` (items S-1 to S-14) and tracker findings F-0009 and F-0010

## Context and problem statement

The agent council's review of `1.0.0-draft.3` ([council report](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/review/council-draft.3.md)) found rules that contradict each other, leave a choice open, or bind the language to one library. Each was asked as a multiple choice with examples, on 2026-11-07. ADR 0017 records the feature decisions (including the new surface of S-5 and S-10); this ADR records the rules.

## Considered options

| Item | Options (chosen in bold) |
|---|---|
| S-1 a `result:` condition error in `until` | **follows `on_body_failure`**; allow `defined` with `result:`; keep and document a probe |
| S-2 retrying a descendant's timeout | **"never" by origin**; keep and use `attempt_timeout` |
| S-3 a cancelled group child in a join | **wait for its `finally`**; the join bound wins; `finally` detaches |
| S-4 the steps when a leaf ends | **drain, stop the tree, then the next sibling**; stop first, then drain; next sibling while stopping |
| S-5 stopping descendants | **split EM-22 by strength, with `detach`**; split, no daemons; keep EM-22 |
| S-6 node-level `concurrency`/`fail_fast` with `for` | **plan error**; node level means the loop; keep and warn |
| S-7 undefined variables before the run | **syntactic scope check**; full flow analysis |
| S-8 `collect` after a failed loop | **always bind, items stay strings**; always bind, JSON values; bind only on success |
| S-9 `defaults.leaf_timeout` on repeating leaves | **per attempt**; total |
| S-10 tempdir removal | see ADR 0017 |
| S-11 `detail.rule` | **rule IDs, with `SY-n` for syntax.md**; slugs |
| S-12 regex dialect | **a portable subset**; .NET semantics |
| S-12 glob case | **case-sensitive everywhere**; follow the file system |
| S-12 Windows output | **implementations SHOULD use UTF-8**; leave it to the plan |
| S-13 `from_env` | **treated like inputs**; honest wording only |
| S-14 `host:` pruning | **shown as pruned, native `arch`**; process `arch`; hidden |

## Decision outcome

All answers follow the recommendation.

- **S-1:** in `until`, a condition error from the `result:` subject (invalid JSON, a path that doesn't resolve) counts as a failed iteration and follows `on_body_failure`: `continue` (the default for `until`) means "not done yet", `stop` fails the node. Each iteration records the error; a loop that ends on `max` or `timeout` reports the last condition error as the cause. Other condition errors, and every condition error in `retry` and `while`, still end the loop.
- **S-2:** "never retried" is decided by origin, not by code. The retrying node's own `timeout`, an ancestor's limit, cancellation and external stops are never retried. A descendant's `timeout` that fires inside an attempt is an ordinary attempt failure: `retry: true` retries it like `BK_TIMEOUT_ATTEMPT`, and its code stays `BK_TIMEOUT_TOTAL`, so conditions see the real cause (EM-66).
- **S-3:** a cancelled child of a join is confirmed when it has completed, its `finally` included (bounded by its `finally_timeout`); the grace period plus the reap timeout bounds each process being killed. Cleanup never overlaps the steps after the join.
- **S-4:** a normative sequence when a leaf's direct child exits: the leaf's duration ends; output is drained until EOF or the drain bound; the remaining tree is stopped unless `keep_descendants` says otherwise; captures and the status are fixed; then the next sibling starts. The teardown time is recorded separately.
- **S-5:** EM-22 is split by strength. MUST: stop everything in the leaf's own OS grouping (process group or session on Unix, job on Windows). SHOULD: the same when the implementation itself is killed, documented per OS by the implementation. Best effort: processes that leave the grouping on purpose. `keep_descendants: detach` (ADR 0017) is the explicit exception.
- **S-6:** node-level `concurrency` and `fail_fast` on a node that has `for` are a plan error; the loop's settings go in `for:`, and an inner group's settings need a child node.
- **S-7:** a reference is a plan error only when no binding of that name can come before it in the plan (a syntactic scope check: typos, wrong names, a capture used before its node). Everything else is checked at run time (`BK_UNDEFINED_VARIABLE` or a condition error). VA-31's branch warning stays a SHOULD; other warnings are optional. The parallel-collision rule covers bindings anywhere in the children's subtrees.
- **S-8:** `collect` always binds its list, also when the loop fails, with `null` for failed, skipped and cancelled iterations: an explicit exception to "captures bind only on success". Items stay strings.
- **S-9:** CO-29 is the probe limit, and hitting it is a condition error. On a leaf with `retry`, `while` or `until`, `defaults.leaf_timeout` limits each attempt or iteration, like an implicit `attempt_timeout`, and fails it with `BK_TIMEOUT_ATTEMPT`.
- **S-10:** the overview no longer says cleanup never needs `rm -rf`; ADR 0017 adds `tempdir.remove`.
- **S-11:** plan errors name the broken rule by its ID in `detail.rule`; syntax.md gets `SY-n` IDs. The conformance feature-id vocabulary is pinned and used for `BK_PLAN_NOT_SUPPORTED`'s `detail.feature`.
- **S-12:**
  - **Regex:** a portable subset close to RE2, defined in syntax.md: literals, `.`, classes, quantifiers, groups, alternation, anchors and inline `(?i)`; `\d`, `\w` and `\s` are ASCII only; `$` matches only at the end of the value; no lookaround, backreferences or atomic groups. Implementations validate a pattern against the subset and translate it for their engine.
  - **Glob:** `*` within a segment, `?`, `[...]`, `**` as a whole segment matching zero or more directories, no braces; matching is ordinal and case-sensitive on every OS.
  - **JSON path:** the ADR 0002 grammar moves into syntax.md.
  - **Windows output:** implementations SHOULD give each Windows leaf UTF-8 output (code page 65001, and `[Console]::OutputEncoding` in the PowerShell prologue); an explicit `encoding:` wins. *Provisional — verify in spike.*
- **S-13:** `from_env` values are known before the run (they read the environment the run started with), so they are treated like inputs: resolved in the validation phase, shown in static views (masked when secret, or marked unset) and part of what a validator sees. An unset name still fails only where it is used (in validation for `vars`, otherwise when its node runs), so the documented guard `when: { env: NAME, defined: true }` keeps working; this refines the recommendation, which had made every unset name a validation error. One wording everywhere: the programs, argv shapes, environments and the source of every value are static; captured values are known only at run time. The run result records each leaf's cwd.
- **S-14:** static views show branches pruned by `host:`, marked as pruned with their condition. `arch` is the OS's native architecture, also when Blokky runs under emulation.

### Consequences

- Good: polls survive a bad response, retried groups retry hung steps, and cleanup never overlaps later work.
- Good: every implementation agrees on plan errors (syntactic scope check, portable regex, glob grammar, rule IDs).
- Good: the "everything a plan executes is visible before it runs" promise holds again, `from_env` included.
- Neutral: joins can take up to a child's `finally_timeout` longer after a cancellation; the timeline shows it.
- Bad: some undefined-variable mistakes are found only at run time; the warnings help but aren't guaranteed.

## More information

- Supersedes the regex dialect of [ADR 0002](0002-language-core.md) (Q3) and the `$` note of CO-14.
- Applied in: `spec/syntax.md`, `spec/reference.md`, `spec/execution-model.md`, `spec/variables.md`, `spec/conditions.md`, `spec/shells.md`, `spec/results.md`, `spec/errors.md`, `spec/glossary.md`, `spec/overview.md`, `schema/blokky.schema.json`, `conformance/README.md`.
- Tracker: T-0051; findings F-0009, F-0010.
