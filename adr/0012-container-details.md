# 0012: Container mount path on Windows and default user (draft round 6)

- Status: accepted; the `container.user` decisions are superseded by [ADR 0017](0017-review-features.md)
- Date: 2026-11-05
- Questions: none from the brief's §4 list; left open by ADR 0005 and raised while drafting `spec/containers.md` (T-0021)

## Context and problem statement

ADR 0005 mounts the cwd "at the same path" by default, which can't work on a Windows host with a Linux container (`C:\src\app` isn't a Linux path); it left that case to the spec. The default user of container processes when `container.user` isn't set was also unspecified. Both were asked as multiple choices with a recommendation, on 2026-11-05.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| Windows host, Linux container: cwd mount path | **drive-letter path (`/c/src/app`)**; fixed `/work`; explicit mounts only |
| Default container user | **the image's default**; the host uid:gid on Unix |

## Decision outcome

Both answers follow the recommendation.

- **Mount path on Windows hosts:** `C:\src\app` maps to `/c/src/app` (lowercase drive letter, forward slashes), the convention of Git Bash and Docker Desktop. With a Windows container the path stays as it is.
- **Default user:** the image's default user, as with `docker run`. A new later lint rule, `container-root-write`, warns when a rootful engine runs as root with a read-write mount, because that leaves root-owned files on the host.

### Consequences

- Good: the default cwd mount works on every host OS.
- Good: container nodes behave like the `docker run` commands users already know.
- Bad: with rootful engines and root images, files written to the workspace are root-owned unless `user` is set; the lint warning points it out.

## More information

- Applied in: `spec/containers.md` CP-10, CP-17.
- Tracker: T-0021.
