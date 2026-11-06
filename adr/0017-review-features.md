# 0017: Review decisions on features

- Status: accepted
- Date: 2026-11-07
- Questions: none from the brief; raised by the agent council's review of `1.0.0-draft.3` (items D-1 to D-6, and the new surface of S-5 and S-10) and by the maintainer (F-0008, F-0011)

## Context and problem statement

The agent council reviewed `1.0.0-draft.3` through five lenses and grouped its findings by the decision each needs ([council report](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/review/council-draft.3.md)). This ADR records the decisions that add, remove or reshape language features. Semantic decisions follow in ADR 0018, corrections in ADR 0019. The questions were asked as multiple choices with examples, on 2026-11-06 and 2026-11-07.

The maintainer set one principle for this batch: a feature that no example uses is a gap in the examples, not a reason to cut it. A cut needs a cost the feature doesn't repay (implementability, safety, rule complexity).

## Considered options

| Item | Options (chosen in bold) |
|---|---|
| D-1 `become` | **cut, not planned**; plain sudo transport for `exec`; keep the trampoline with a sudo-like environment |
| D-2 `container` | cut; **keep, smaller, decide again after the spikes**; keep as is |
| D-2 `container.user` | **drop it, map the invoking user**; keep it; decide after the spike |
| D-3 `services` | **drop `depends_on`, keep `on_exit` and `output:`**; also drop `on_exit`; also drop `output:` |
| D-4 `while`, `on_body_failure` | **keep both, fix the examples**; keep `while` only; cut both |
| D-4 rebinding for pagination | **single assignment plus loop-carried variables**; carry later; mutable variables |
| D-4 `carry` syntax | **`carry: { CURSOR: NEXT }` next to `collect`**; `feed`; one merged key; `initial` required |
| D-4 iteration index | named, on `while`/`until`; **named, also on `retry`**; 0-based only; none |
| D-5 small items | see below |
| D-6 early exit | **a `return` kind**; none |
| S-5 daemons | **`keep_descendants: detach`**; out of scope |
| S-10 tempdir removal | **`remove: true \| on_success`**; `remove: true`; remove by default; wording only |

## Decision outcome

### D-1 `become` is cut

`become`, `defaults.become`, `invoker`, the privilege-drop mode and their error codes are removed, and they are not ROADMAP candidates. As specified, `become` was less safe than `sudo -n` in bash: the leaf kept the caller's environment and PATH whatever sudo's policy said, the trampoline had to be allowed in sudoers (the same as allowing every command), and sudo's log showed only the trampoline. Plans write `exec: [sudo, -n, …]`, which is exactly bash: sudo's rules, environment reset, `secure_path` and log all apply. Every process a plan starts runs as the user Blokky runs as.

### D-2 `container` is kept, smaller, and decided again after the spikes

- **Compatible images only.** The image provides `sh`, `sleep` and `kill`; Blokky ships no in-container helper. An image without them fails when the container starts, with an error that names what is missing. Distroless and chiseled images are not supported.
- **Env values never go on a command line.** They reach the container through an env file (mode 0600) passed to the engine's `exec --env-file`.
- **No relabelling.** Blokky never relabels host paths. Ownership and labelling of mounts are engine-defined; the run result says when labelling was disabled for Blokky's own mounts.
- **`env_pass` stays** as a shorthand for `env: { NAME: { from_env: NAME } }`, like `export` for plan variables.
- **`user` is dropped.** The goal it served, running builds in non-root images that write the cwd mount, is a question of UID mapping, not of a plan field. The implementation maps the invoking user into the container where the engine allows it (rootless Podman: `--userns=keep-id`; rootful Docker: `--user` with the invoking UID and GID). This is provisional: the engine-matrix spike verifies it with non-root build images, and `user` comes back only if plans need to choose.

The whole feature is decided again after the container spikes; if they show it is too costly, a later draft cuts it.

### D-3 `services` start in list order

`depends_on` is dropped: services start one at a time in list order, each ready before the next starts, and stop in reverse order. Both examples had a linear chain, which list order expresses directly. `on_exit` stays (helper services such as a mail catcher or a port-forward that may drop), and so does the `output:` readiness subject (a port check passes for any process on the port).

### D-4 `while`, `on_body_failure` and loop-carried variables

- `while` stays for work loops that must not run when there is no work (zero iterations); `on_body_failure` stays because `until` + `stop` makes a poll fail at once on a permanent error instead of after its timeout. The examples are fixed to show both.
- **Single assignment stays.** General rebinding would give up one definition per value in static views, race freedom in parallel groups, a simple undefined-variable check, fixed secrecy per binding and clean failed attempts, for one pattern.
- **`carry`** on `while` and `until`: `carry: { CURSOR: NEXT }` binds `CURSOR` once per iteration, `''` in the first and then the value of the previous iteration's `NEXT` capture. The long form `{ from: NEXT, initial: '…' }` sets another first value. Within an iteration the name is bound once, so single assignment holds; its origin is static ("the initial value, or the previous `NEXT`").
- **`collect`** becomes valid on `while` and `until`, with the same shape and rules as on `for`.
- **`index`** on `while`, `until` and `retry`: `index: NAME` binds the 0-based iteration or attempt number; the long form `{ as: NAME, start: 1 }` sets the first value. It covers page-number APIs, since templates have no arithmetic.

```yaml
- until: { var: NEXT, empty: true }
  carry: { CURSOR: NEXT }        # '' in iteration 1, then the previous NEXT
  collect: { PAGES: PAGE }       # every PAGE, as a list, after the loop
  max: 100
  do:
    - exec: [./fetch-issues, --cursor, { var: CURSOR }]
      capture:
        PAGE: { json: .items }
        NEXT: { json: .next_cursor }
```

### D-5 Smaller items

- Kept: `matrix`, `allow_empty`, `keep_blank`, `jitter`, all four `encoding` values, `{ var }` in `set`/`vars`, `race`, `zsh`.
- `max_items` applies to every `for` source (for `matrix`: the number of combinations).
- `max_log_bytes` moves out of the language: how much output an implementation keeps is its configuration (ADR 0013's scope rule). The size grammar goes with it.
- `fish` is cut: it is non-POSIX, has no error mode, and is rarely used for scripts.

### D-6 `return`

`return: "message"` is a node kind that ends the nearest enclosing `do` sequence successfully: the plan's top-level `do`, a `do` group, or a loop body (where it ends the iteration, like `continue`). The siblings after it are `skipped` with `skip_reason: returned`. `if` branches are transparent: a `return` in `then` or `else` ends the `do` that contains the `if`. There is no `break`. A `return` whose nearest sequence lies beyond an `all`, `any` or `race` is a plan error. A `return` without `when` that isn't inside an `if` branch gets a warning. Inside `finally`, `return` ends that `finally` list.

### S-5 `keep_descendants: detach`

A plan may deliberately leave a process running after the run, as `nohup x &` does in bash: `keep_descendants: detach` exempts the leaf's remaining processes from every stop, including the end of the run. Static views show it, and the run result lists what was left running. `true` keeps meaning "until the run ends".

### S-10 `tempdir` removal

`tempdir: { remove: true }` deletes the directory at node end, after `finally`; `remove: on_success` deletes it only when the node succeeded, so a failure can be inspected. Removal never follows links. Without `remove`, the directory stays for the implementation's cleanup, as before.

### Consequences

- Good: no feature runs a plan with less safety than bash; the largest provisional area (`become`) is gone.
- Good: pagination, work loops, early exits and daemons can be written without a shell.
- Good: single assignment and its static properties survive.
- Neutral: `container` stays provisional until the spikes.
- Bad: three new constructs (`return`, `carry`, `index`) and a new `tempdir` option add to the language's size; the review weighed them against the patterns they remove.

## More information

- Supersedes the `become` parts of [ADR 0005](0005-containers-become-locks.md), the `container.user` default of [ADR 0012](0012-container-details.md), and `depends_on` and `fish` in [ADR 0014](0014-remaining-features.md).
- Applied in: `spec/containers.md` (renamed from `containers-and-privilege.md`), `spec/reference.md`, `spec/syntax.md`, `spec/execution-model.md`, `spec/variables.md`, `spec/conditions.md`, `spec/shells.md`, `spec/results.md`, `spec/errors.md`, `spec/glossary.md`, `spec/overview.md`, `schema/blokky.schema.json`, `examples/`, `conformance/`, `ROADMAP.md`.
- Tracker: T-0051; findings F-0008, F-0009, F-0011.
