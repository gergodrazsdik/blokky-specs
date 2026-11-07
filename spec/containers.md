# Containers

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is normative for the language-level behaviour of the `container` modifier: its shape, the path model, mounts, the environment, scoping and interactions. Engine detection and termination inside containers depend on spikes and are specified in the blokky-cli design notes; statements marked *provisional — verify in spike* depend on spike results. The whole feature is decided again after the container spikes ([ADR 0017](../adr/0017-review-features.md)). Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions). Rules carry IDs (`CP-n`); IDs of removed rules are not reused.

Decisions: [ADR 0005](../adr/0005-containers-become-locks.md), [ADR 0012](../adr/0012-container-details.md), [ADR 0017](../adr/0017-review-features.md), [ADR 0026](../adr/0026-runtime-edge-cases.md).

## 1. Path model

- **CP-1.** `path:` subjects, `for: { glob }`, `tempdir`, `cwd` (except an absolute `cwd` under a container that isn't under a mount, CP-14), `capture_file`, `stdin: { file }` and `mounts[].host` are **host** paths, evaluated on the host, whether or not a node runs in a container.
- **CP-2.** Under `container`, only processes run inside the container: leaves, probes and services. A `path:` condition on a container node still checks the host; implementations SHOULD warn about it.
- **CP-41.** **Path forms.** A container path is a POSIX path and is absolute when it starts with `/`, on every host OS, Windows included. A host path is absolute by the host OS's rules (on Windows, a drive-letter path such as `C:\src` or a UNC path), so `/src` is never an absolute host path on Windows.

## 2. `container`

### 2.1 Shape

```yaml
- name: build in the SDK image
  container:
    image: mcr.microsoft.com/dotnet/sdk:10.0
    mounts:
      - { host: ., path: /src }
      - { host: { var: NUGET_CACHE }, path: /home/app/.nuget/packages }
    env_pass: [NUGET_API_KEY]
  cwd: /src                          # see CP-14
  exec: [dotnet, build, -c, Release]
```

| Field | Required | Value |
|---|---|---|
| `image` | yes | An image reference (literal, [syntax.md §6.10](syntax.md#610-image-references), SY-103). |
| `mounts` | no | A list of `{ host, path, read_only }` mappings; an empty list is allowed. |
| `env_pass` | no | Names of environment variables passed from the environment the run started with into the container. |

- **CP-40.** **Required keys.** `container` has `image`, and every `mounts` entry has `host` and `path`. A missing one is a plan error (`BK_PLAN_INVALID`, this rule); the schema enforces it too.
- **CP-3.** There is only **ephemeral** mode: Blokky starts one container for the node. There is no mode for running in an existing container; a plan that needs one calls the engine itself (`exec: [docker, exec, …]`).

### 2.2 Lifecycle

- **CP-4.** The container starts when the node is entered (after `lock`, `tempdir`, `cwd` and `env`; [execution-model.md](execution-model.md)), within the node's `timeout`, and runs an idle process. Each leaf, probe and service under the node runs in it through `<engine> exec`.
- **CP-36.** **Compatible images.** The image MUST provide `sh`, `sleep` and `kill` on its `PATH`: the idle process and in-container termination use them, and Blokky adds no helper to the container. An image without them fails the node when the container starts, with `BK_CONTAINER_FAILED` and `detail.missing`, the list of the missing program names (`[kill]`). Images without a shell (distroless, chiseled) are not supported.
- **CP-5.** At node end (after `finally`), the container is **stopped, not removed**, so it can be inspected. Removing it later is the implementation's business (for blokky-cli: `blokky clean`).
- **CP-6.** The run result records the engine, the image digest and the container id. The engine commands the implementation issues are part of what the plan executes, and are visible before the run like any other process ([reference.md §9](reference.md#9-security-considerations)).
- **CP-7.** The engine CLI is started with Blokky's own environment, not the node's `env`, so a node can't redirect it (for example with `DOCKER_HOST`). Which engines an implementation supports and how it chooses one is implementation-defined (for blokky-cli: its configuration and detection, decided after the engine spike).
- **CP-8.** Terminating a leaf inside a container uses an in-container process group with a recorded PID: TERM, grace period, KILL through `<engine> exec … kill`, and stopping the container as the fallback. *Provisional — verify in spike.*

### 2.3 Mounts

- **CP-9.** **Default mount.** When `mounts` is not given, the **cwd the node inherits** (its parent's effective cwd; at the root, the invocation cwd) **is mounted read-write at the same path**, wherever it is; Blokky doesn't assume a git repository. The node's own `cwd` doesn't change what is mounted: CP-14 maps it through this mount.
- **CP-10.** **Path mapping.** "The same path" means the host path on Linux and macOS. On a Windows host with a Linux container, a host path `C:\src\app` maps to `/c/src/app` (lowercase drive letter, forward slashes); with a Windows container it stays as it is.
- **CP-11.** **Runtime mounts** are always added: the run's scripts dir, read-only, at a fixed container path; and the node's own `tempdir`, read-write at the same path, when the node has one (it is the node's cwd, so the container cwd maps through it, CP-14).
- **CP-12.** **Explicit mounts.** A `mounts` list replaces the default cwd mount; it doesn't add to it. `mounts: []` mounts only the runtime dirs.
- **CP-13.** Each entry is `{ host, path, read_only }`: `host` is a host path (literal or `{ var: X }`), relative paths resolve against the **invocation** cwd; `path` is an absolute container path (literal, starting with `/`, CP-41); `read_only` defaults to `false`.
- **CP-14.** **The container cwd** is the container path the node's effective cwd maps to through the mounts (the default mount, CP-9, or the explicit ones). A relative `cwd` on the node resolves against the cwd it inherits, as on the host, and then maps. The node's own absolute `cwd` is a host path if it is under a mount's host path, and maps through that mount; otherwise, if it is an absolute container path (CP-41), it is a container path, checked inside the container. An absolute host path under no mount that isn't an absolute container path (`C:\work` on a Windows host) maps through no mount. A cwd that maps through no mount is an error, `BK_CWD_UNMAPPED` ("add a mount for … or set `cwd` to a container path").
- **CP-37.** **Labels and ownership.** Blokky MUST NOT relabel host paths (no `:z`/`:Z`, which change labels on the host). Ownership, UID mapping and SELinux labelling of mounts are engine-defined. An implementation MAY disable labelling for the mounts it adds; the run result says so.

### 2.4 Inside the container

- **CP-15.** `exec` argv[0] resolves **inside** the container (the engine's lookup), not on the host. `script` leaves need their shell in the image; the script file is read from the read-only scripts mount. Shell detection (SH-22) runs inside the image: `bash`, else `sh`. A container leaf whose argv[0] isn't in the image fails with `BK_SPAWN_NOT_FOUND` (`detail.program`: argv[0] as written); one whose script shell isn't in the image fails with `BK_SHELL_UNAVAILABLE`. Implementations map the engine's not-found result to these codes.
- **CP-16.** A container process's environment is the image's environment, plus the output defaults of VA-44 (`NO_COLOR=1`, and `TERM=dumb` when the image's environment has no `TERM`), plus the scoped `env` and `export` mappings of the node and its ancestors, plus the `env_pass` names (taken from the environment the run started with; a name that isn't set there is not passed, without an error), plus the `BLOKKY_*` variables. The host environment is not passed otherwise. `env_pass: [X]` is a shorthand for `env: { X: { from_env: X } }` without the error for an unset name.
- **CP-42.** **`env_pass` names follow the rules of `env` and `export`.** `env_pass` passes a host variable through, like `export`, so a forbidden name (VA-41, as for `env`) or a reserved name (VA-42, as for `export`) is a plan error, and so is a name both in `env_pass` and in `env` or `export` on the same node; each is reported as RF-10. On Windows hosts, names are compared case-insensitively.
- **CP-38.** **Transport.** Environment values MUST NOT appear on any command line, the engine's included: they reach the container through a run-owned env file (readable only by the run's user) passed to the engine's `exec --env-file`, or an equivalent that keeps them off command lines. The run result's `invocation` of a container leaf is the argv run inside the container, not the engine command (results.md §3.1).
- **CP-17.** **User.** Processes run as the image's default user, as with `docker run`. Where the engine allows it, the implementation maps the invoking user into the container (rootless Podman: `--userns=keep-id`; rootful Docker: `--user` with the invoking UID and GID), so a build in a non-root image can write the cwd mount and its files are owned by the invoking user. *Provisional — verify in spike* with non-root build images. On a rootful engine without such mapping, running as root with a read-write mount creates root-owned files on the host; implementations SHOULD warn about it.
- **CP-18.** Probes on a container node run inside the container (they are processes). `when` is evaluated in the parent's scope, outside the container.

### 2.5 Nesting

- **CP-19.** A node inside a `container` node runs in that container. A `container` on a node inside another container's scope is a plan error.

### 2.6 Security

Containers are not a sandbox by default. Mounting the engine socket, adding capabilities or running privileged is equivalent to host root; implementations SHOULD flag engine-socket mounts. The default read-write cwd mount gives the container the same access to the workspace as a host leaf. Blokky never uses a container to decide what is allowed.

## 3. Users

- **CP-39.** Every process a plan starts on the host runs as the user Blokky runs as. The language has no way to switch users: a plan that needs another user runs `sudo -n` or `doas -n` in a leaf, exactly as in bash, where the elevation tool's own rules, environment policy and log apply ([ADR 0017](../adr/0017-review-features.md)).
