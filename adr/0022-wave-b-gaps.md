# 0022: Gaps found by the wave B conformance cases

- Status: accepted
- Date: 2026-11-07
- Questions: none from the brief; raised while writing and checking the wave B run-semantics cases (tracker T-0062, F-0018; [review notes](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/review/conformance-wave-b.md))

## Context and problem statement

Three agents wrote the wave B cases (kinds and status, leaf processes, variables at run time), and three more read them against the spec. Wrong cases were fixed. Before listing a gap, the main agent checked its premise against the cited text and ADRs, and dropped one gap as a misreading. The remaining gaps leave run results undetermined. The maintainer decided E-1 and E-2 and accepted the batch C-1 to C-5 on 2026-11-07.

## Considered options

| Item | Options (chosen in bold) |
|---|---|
| E-1 nodes of an `if` branch that didn't run | **present, `skipped` with skip reason `not_taken`**; absent |
| E-2 a failing node in `then`/`else`/`finally` | **branches stop like `do`; `finally` runs every node**; all stop; all run every node |
| C-1 to C-5 | **accepted as a batch** |

## Decision outcome

- **E-1.** The nodes of the branch that didn't run are in the run result as `skipped`, with skip reason `not_taken` (reference.md §2.7, EM status table, results.md).
- **E-2.** A `then` or `else` branch stops at its first failure, like a `do` with `fail_fast: true`. A `finally` list runs every node, so each cleanup step is tried, and fails with its first failure (reference.md §4.10).
- **C-1 Captures.**
  - The NUL check is on the decoded text (VA-21), and trimming happens after decoding (VA-20).
  - Field captures run the VA-21 checks first (VA-22).
  - `BK_CAPTURE_PATH` `detail.path` is the path as written.
- **C-2 Compact JSON** is defined once, in SY-86: RFC 8259 text, no insignificant whitespace, members in input order, numbers as written, short escapes, `\u00XX` for other control characters.
- **C-3 Results.**
  - RS-6 lists the fields of a node that never started.
  - Repetition entries are in index order.
  - The run has an `id`.
  - The result document gets `id`, `children` (to assert plan order) and `left_running`.
  - Causes that a group attaches (EM-51, EM-52) belong to the group's error only (EM-66).
- **C-4 Leaves.**
  - In `invocation`, element 0 is argv[0] as written.
  - Defined detail values for `BK_SPAWN_NOT_FOUND`, `BK_SPAWN_FAILED` and `BK_SIGNAL`.
  - `stdin` text is passed as exact UTF-8 bytes.
  - The drain bound is at least 1s (EM-20).
  - A `return` message is recorded at level `info`.
- **C-5 Conformance format.**
  - `after:` is in plan time (CF-22).
  - Cases with `spawn`, `actions` or `after_run` default to `clock: [real]` (CF-40).
  - Conformance runs use the language's default bounds (CF-57).
  - The testkit gets `symlink` (TK-22), for EM-69.
  - RS-4 and VA-53 are exempt.

### Consequences

- Good: the wave B cases assert results that are fully determined, and the result document can show plan order and the path not taken.
- Good: cleanup in `finally` tries every step, which matches what users expect from cleanup code.
- Neutral: implementations record one more skip reason, and testkits implement one more command.

## More information

- Applied in: `spec/reference.md`, `spec/execution-model.md`, `spec/results.md`, `spec/errors.md`, `spec/variables.md`, `spec/syntax.md`, `conformance/README.md`, `conformance/case.schema.json`, `conformance/testkit-interface.md`.
- Tracker: T-0062; finding F-0018.
