# 0026: Runtime edge cases after the wave E cases

- Status: accepted
- Date: 2026-11-07
- Questions: none from the brief; the points the wave E combination and container cases left open (tracker F-0022, F-0023).

## Context and problem statement

The wave E cases ([ADR 0025](0025-open-points.md)) left points that no case asserts because the spec doesn't decide them: whether `finally` runs when a layer outside it fails the node, whether services stop when the node's own `timeout` fires, what a node skipped or failed by `when` records, a few repetition and lock details, and several container points (the default mount for an absolute `cwd`, missing programs in the image, `env_pass` overlaps, the image grammar, the result's `container` field). The maintainer decided all points as recommended on 2026-11-07.

## Considered options

| Item | Options (chosen in bold) |
|---|---|
| R-1 `finally` after an outer layer fails | **`finally` runs only when the node got past every layer outside it; otherwise it is skipped and records no status**; `finally` always runs once the node started |
| R-2 services when the node's own `timeout` fires | **only the body is stopped; services keep running for `finally` and stop after it**; everything under the node stops at once (EM-26 read literally) |
| R-3 a node skipped by `when` | **only the node itself appears**; the whole subtree appears as `skipped` |
| R-4 the default mount | **the cwd the node inherits, at the same path; the node's own absolute `cwd` is a host path under that mount, else a container path**; the node's own effective cwd |
| R-5 missing programs in the image | **`BK_SPAWN_NOT_FOUND` and `BK_SHELL_UNAVAILABLE`, mapped from the engine; detection inside the image**; `BK_CONTAINER_FAILED` |
| R-6 `env_pass` | **follows `env`'s rules (RF-10)**; no checks |
| R-7 the remaining details | **accepted as recommended** |

## Decision outcome

- **R-1 `finally` and the outer layers.** `finally` runs inside every layer outside it (EM-4, EM-7), so it runs only when the node got past all of them. When the lock wait, tempdir, cwd, env, container or services fail the node, or the node's `timeout` or a cancellation fires during them, the body and `finally` don't run: their nodes are `skipped` with `not_reached`, and no `finally` status is recorded. EM-63, which said this for services, now says it for every outer layer (EM-7, EM-63, reference.md §4.3, §4.4, §4.10).
- **R-2 Services and the node's timeout.** Services belong to the node's scope, not to its body. When the node's own `timeout` fires while the body runs, the body's processes are stopped; services keep running so that `finally` can use them, and are stopped after it. EM-26's "every process tree under that limit" means the body's processes for a node's own `timeout` (EM-26, EM-65, reference.md §4.3, §4.9).
- **R-3 A node skipped by `when`.** Only the node itself appears in the run result: id, kind, name, status `skipped`, skip reason `condition`, its `when` probes. Its descendants and `finally` nodes are absent (new RS-7; RS-3, EM-5, reference.md §4.2).
- **R-4 The default mount.** Without `mounts`, the cwd the node inherits (its parent's effective cwd) is mounted at the same path. The node's own absolute `cwd` is a host path if it is under a mount, else a container path (CP-9, CP-11, CP-14, reference.md §4.6, §4.8).
- **R-5 Missing programs.** A container leaf whose argv[0] isn't in the image fails with `BK_SPAWN_NOT_FOUND` (`detail.program` as written); a missing script shell with `BK_SHELL_UNAVAILABLE`. Implementations map the engine's not-found result. Shell detection for a container leaf runs inside the image: `bash`, then `sh` (CP-15, SH-22, EM-14, errors.md §5.1).
- **R-6 `env_pass`.** A name in `env_pass` and in `env` or `export` on one node is RF-10; a forbidden name is an error as in `env` (VA-41) and a reserved name as in `export` (VA-42), since `env_pass` passes a host variable through like `export`; both are reported as RF-10 (new CP-42, RF-10, errors.md §4).
- **R-7 Details.**
  - (a) A node that fails before its first attempt or iteration records `repetition: { count: 0, ended_by: failure }` (results.md §3).
  - (b) An attempt interrupted by the node's own `timeout` is `cancelled` (EM-53, results.md §3, reference.md §4.3).
  - (c) A node that fails in `when` records its error and `when` probes only (new RS-8, EM-47).
  - (d) A lock waiter checks again at most 250ms after its previous check, as for readiness (EM-60, reference.md §4.4).
  - (e) Image references follow the OCI grammar `[registry/]name[:tag][@digest]`; others are `BK_PLAN_VALUE` (new SY-103, syntax.md §6.10).
  - (f) A missing `image` or mount `path` (or `host`) is `BK_PLAN_INVALID` with new CP-40, which states that the keys are required; before, only the field table and the schema did.
  - (g) The result's `container` field is `{ engine, image_digest, id, labelling_disabled }` (results.md §3.1, conformance/README.md §3.6).
  - (h) CP-36's `detail.missing` is a list of program names (errors.md §5.5).
  - (i) CP-10 no longer mentions "container-side defaults of `{ var }` host paths", which no rule defines.
  - (j) A container leaf's `invocation` is the in-container argv, not the engine command (results.md §3.1, CP-38).
  - (k) Container paths are POSIX paths, absolute when they start with `/`, on every host; host paths are absolute by the host OS's rules (new CP-41, CP-13, reference.md §4.6).

Settled when checking the cases: an absolute Windows host `cwd` under no mount maps through no mount and is `BK_CWD_UNMAPPED` (CP-14); `count: 0` also covers a `for` that fails while evaluating its items (results.md).

### Consequences

- Good: every point F-0022 and F-0023 list has one answer a conformance case can assert.
- Good: `finally` can rely on its services after the node's own timeout, as cleanup that talks to a database or a mock usually needs.
- Neutral: a node that fails before its body runs no cleanup of its own; cleanup that must always run belongs on an ancestor.
- Neutral: run results get smaller below nodes skipped or failed by `when`; cases that asserted their descendants need updating.

## More information

- Applied in: `spec/execution-model.md`, `spec/results.md`, `spec/reference.md`, `spec/containers.md`, `spec/errors.md`, `spec/syntax.md`, `spec/shells.md`, `conformance/README.md`.
- New rules: CP-40, CP-41, CP-42, RS-7, RS-8, SY-103.
- Tracker: findings F-0022 and F-0023.
