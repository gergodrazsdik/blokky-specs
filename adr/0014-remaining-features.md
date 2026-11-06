# 0014: Remaining language features (batch 7)

- Status: accepted; `depends_on` and `fish` are superseded by [ADR 0017](0017-review-features.md)
- Date: 2026-11-05
- Questions: Q18 (out-of-band consent); the open details of `race`, `lock`, `services`, `for` sources, `collect` and the `zsh`/`fish` shells, raised for T-0047 (brief §8 step 5)

## Context and problem statement

Before `1.0.0-draft.1`, every planned feature must be specified to the same depth ([ADR 0013](0013-scope-and-versioning.md)). These features were still sketches: `race`, `lock`, `services`, `for` over `items`/`lines`/`matrix`, `collect`, `consent`, and the `zsh`/`fish` shells. The open details were asked in five rounds of multiple choices with examples, on 2026-11-05.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| `race`: skipped children and ignored failures | **like `do`/`any`: skipped children don't take part, an ignored failure decides like a success**; an ignored failure keeps the race waiting |
| `race`: captures | **only the deciding child's**; no captures in `race` |
| `lines`: splitting | **LF (CRLF tolerated), blank lines dropped**, with the maintainer's addition `keep_blank: true`; keep blank lines; trim each line |
| `matrix`: exclude/include | **plain product only**; exclude only; exclude and include |
| `items`: reaching fields | **`fields: { NAME: .path }` on the `for`**; `json:` on any reference; scalar items only |
| `collect`: value form | **a JSON array**; lines |
| `lock`: scope | **per user, machine-wide**; per repository; machine-wide for all users |
| `lock`: without `wait` | **wait as long as the node's `timeout` allows**; try once; wait 5m |
| `lock`: modes | **exclusive only**; exclusive and shared |
| `services`: start order | in list order, each ready first; all at once; **in parallel, with `depends_on`** |
| `services`: a ready service exits | fail the node; record only; **per service: `on_exit: fail \| ignore`** |
| `services`: readiness | **`ready:` required, `ready_timeout` 30s, polled every 250ms**; `ready:` optional; configurable interval |
| `services`: what the plan sees | **status only, no variables**; status plus a capture from the ready output |
| `consent` | **drop from 1.0** (ROADMAP candidate); specify now; keep reserved |
| `zsh` and `fish` | **add both rows**; `zsh` only; drop both |

## Decision outcome

Most answers follow the recommendation. The maintainer chose differently for service start order (parallel with `depends_on`) and for a ready service exiting (per-service `on_exit`), and added `keep_blank` to `lines`.

### `race`

Skipped children don't take part; an ignored failure that finishes first decides like a success; a race whose children were all skipped succeeds. Only the deciding child's captures are bound; children may capture the same name. If the decider failed, nothing is bound and the race fails with the decider's error.

### `for` sources and `collect`

- **`lines`:** the value is split on LF, a CR before each LF is removed, and lines that are empty or only whitespace are dropped unless `keep_blank: true`. Line content is kept exactly.
- **`matrix`:** the plain Cartesian product in key order, the first key varying slowest. Combinations are skipped with a `when` inside the loop body.
- **`items`:** the path must select a JSON array. Each element is converted to a string as in field captures. The new `for` option `fields: { NAME: .path, … }` binds variables from each item per iteration; a path that doesn't resolve for an item fails that iteration.
- **`collect`:** the list variable holds a compact JSON array of strings in item order, with `null` for failed or skipped iterations.

### `lock`

- Lock names form one namespace per OS user on the machine: the same name in any plan, repo or run of that user is the same lock; other users' locks never interact.
- Without `wait`, a node waits as long as its `timeout` (and any external stop) allows; `wait: 0s` tries once.
- Locks are exclusive.

### `services`

- **Start order:** services start in parallel. A service with `depends_on: [NAME, …]` starts only after those services are ready. Service `name`s are therefore required and unique within a node, and dependencies must not form a cycle (both plan errors).
- **Stop order:** stopping happens in reverse dependency order.
- **Readiness:** `ready:` is required. `ready_timeout` defaults to 30s, within the node's `timeout`. The condition is polled every 250ms.
- **Exits:** a service that exits before it is ready fails the node (`BK_SERVICE_NOT_READY` or `BK_SERVICE_EXITED`). A service that exits on its own after it was ready follows its `on_exit`: `fail` (the default) cancels the body and fails the node with `BK_SERVICE_EXITED`; `ignore` records the exit and continues.
- **What the plan sees:** services bind no variables. The run result records each service's readiness time and how it ended.

### `consent`

Dropped from 1.0. The keyword is no longer reserved and is listed as a ROADMAP candidate. 1.0 stays non-interactive; `become` stays Unix-only and passwordless; Windows elevation uses the handoff pattern of the implementation's docs.

### `zsh` and `fish`

| Shell | Invocation | Error handling |
|---|---|---|
| `zsh` | `zsh --no-rcs -o pipefail <file>` | `pipefail`; no `-e`, no `-u` |
| `fish` | `fish --no-config <file>` | none; `$pipestatus` and `$status` are available |

Both are Unix-only and used only when named; detection never picks them.

### Consequences

- Good: every feature of the language is specified; `1.0.0-draft.1` can be tagged after this lands.
- Good: `services` cover dependent services without ordering tricks.
- Neutral: skipping a `matrix` combination takes a nested node with `when`.
- Bad: `services` gain two fields (`depends_on`, `on_exit`) and cycle checks; the review should look at whether services earn their size.

## More information

- Applied in: `spec/reference.md` (§2.6, §4.4, §4.10, §5.7), `spec/execution-model.md` (EM-58 to EM-65), `spec/variables.md` (bindings, VA-30, VA-54, VA-55), `spec/conditions.md` (`port`, `output`), `spec/shells.md`, `spec/syntax.md`, `spec/errors.md`, `spec/results.md`, `schema/blokky.schema.json`, `ROADMAP.md`.
- Tracker: T-0047, T-0048.
