# Containers and privilege

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is normative for the language-level behaviour of the `container` and `become` modifiers: value shapes, the path model, mounts, users, scoping and interactions. Engine detection, termination inside containers and killing across a privilege boundary depend on spikes and are specified in the blokky-cli design notes; statements marked *provisional — verify in spike* depend on spike results. Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions). Rules carry IDs (`CP-n`).

Decisions: [ADR 0005](../adr/0005-containers-become-locks.md), [ADR 0012](../adr/0012-container-details.md).

## 1. Path model

- **CP-1.** `path:` subjects, `for: { glob }`, `tempdir`, `cwd`, `capture_file`, `stdin: { file }` and `mounts[].host` are **host** paths, evaluated on the host, whether or not a node runs in a container.
- **CP-2.** Under `container`, only processes run inside the container: leaves, probes and services. A `path:` condition on a container node still checks the host; implementations SHOULD warn about it.

## 2. `container`

### 2.1 Shape

```yaml
- name: build in the SDK image
  container:
    image: mcr.microsoft.com/dotnet/sdk:10.0
    mounts:
      - { host: ., path: /src }
      - { host: { var: NUGET_CACHE }, path: /root/.nuget/packages }
    user: '1000:1000'
    env_pass: [NUGET_API_KEY]
  cwd: /src                          # see CP-10
  exec: [dotnet, build, -c, Release]
```

| Field | Required | Value |
|---|---|---|
| `image` | yes | An image reference (literal). |
| `mounts` | no | A list of `{ host, path, read_only }` mappings; an empty list is allowed. |
| `user` | no | A user for the container's processes (literal, as the engine accepts it: `name`, `uid`, `uid:gid`). |
| `env_pass` | no | Names of environment variables passed from Blokky's environment into the container. |

- **CP-3.** There is only **ephemeral** mode: Blokky starts one container for the node. There is no mode for running in an existing container; a plan that needs one calls the engine itself (`exec: [docker, exec, …]`).

### 2.2 Lifecycle

- **CP-4.** The container starts when the node is entered (after `lock`, `tempdir`, `cwd` and `env`; [execution-model.md](execution-model.md)), within the node's `timeout`, and runs an idle process. Each leaf, probe and service under the node runs in it through `<engine> exec`.
- **CP-5.** At node end (after `finally`), the container is **stopped, not removed**, so it can be inspected. Removing it later is the implementation's business (for blokky-cli: `blokky clean`).
- **CP-6.** The run result records the engine, the image digest and the container id. The engine commands the implementation issues are part of what the plan executes, and are visible before the run like any other process ([reference.md §9](reference.md#9-security-considerations)).
- **CP-7.** The engine CLI is started with Blokky's own environment, not the node's `env`, so a node can't redirect it (for example with `DOCKER_HOST`). Which engines are supported and how one is chosen is a later question (Q16b).
- **CP-8.** Terminating a leaf inside a container uses an in-container process group with a recorded PID: TERM, grace period, KILL through `<engine> exec … kill`, and stopping the container as the fallback. *Provisional — verify in spike*, including images without a shell or `kill`.

### 2.3 Mounts

- **CP-9.** **Default mount.** When `mounts` is not given, the node's effective **cwd is mounted read-write at the same path**, wherever it is; Blokky doesn't assume a git repository.
- **CP-10.** **Path mapping.** "The same path" means the host path on Linux and macOS. On a Windows host with a Linux container, a host path `C:\src\app` maps to `/c/src/app` (lowercase drive letter, forward slashes); with a Windows container it stays as it is. The same mapping applies to the container-side defaults of `{ var }` host paths.
- **CP-11.** **Runtime mounts** are always added: the run's scripts dir, read-only, at a fixed container path; and the node's own `tempdir`, read-write, when the node has one (it is the cwd, so it is the cwd mount).
- **CP-12.** **Explicit mounts.** A `mounts` list replaces the default cwd mount; it doesn't add to it. `mounts: []` mounts only the runtime dirs.
- **CP-13.** Each entry is `{ host, path, read_only }`: `host` is a host path (literal or `{ var: X }`), relative paths resolve against the **invocation** cwd; `path` is an absolute container path (literal); `read_only` defaults to `false`.
- **CP-14.** **The container cwd** is the container path the node's effective cwd maps to through the mounts. A cwd that maps through no mount is an error ("add a mount for … or set `cwd` to a container path"). An absolute `cwd` that isn't a host path under a mount is taken as a container path.

### 2.4 Inside the container

- **CP-15.** `exec` argv[0] resolves **inside** the container (the engine's lookup), not on the host. `script` leaves need their shell in the image; the script file is read from the read-only scripts mount.
- **CP-16.** A container process's environment is the image's environment, plus the scoped `env` and `export` mappings of the node and its ancestors, plus the `env_pass` names (taken from the environment the run started with; a name that isn't set there is not passed, without an error), plus the `BLOKKY_*` variables. The host environment is not passed otherwise.
- **CP-17.** **User.** Without `user`, processes run as the image's default user, as with `docker run`. On a rootful engine, running as root with a read-write mount creates root-owned files on the host; implementations SHOULD warn about it.
- **CP-18.** Probes on a container node run inside the container (they are processes). `when` is evaluated in the parent's scope, outside the container.

### 2.5 Nesting

- **CP-19.** A node inside a `container` node runs in that container. A `container` on a node inside another container's scope is a plan error.
- **CP-20.** `become` and `container` don't combine: `become` on a node inside a container's scope, or `container` inside a `become` scope, is a plan error. Use `container.user` instead.

### 2.6 Security

Containers are not a sandbox by default. Mounting the engine socket, adding capabilities or running privileged is equivalent to host root; implementations SHOULD flag engine-socket mounts. The default read-write cwd mount gives the container the same access to the workspace as a host leaf. Blokky never uses a container to decide what is allowed.

## 3. `become`

### 3.1 Shape

```yaml
blokky: 1.0
defaults:
  become: invoker               # as root: drop to the sudo/doas caller
do:
  - exec: [make, build]         # runs as the invoking user
  - name: install
    become: root
    exec: [make, install]
```

- **CP-21.** `become: USER`, `become: invoker` or `become: { user: USER }` (literal). `defaults.become` takes the same values and applies to every leaf and probe without its own `become`.
- **CP-22.** Implementations MAY require an explicit opt-in by the user before `become` is used; without it, a plan using `become` fails before it runs (`BK_BECOME_DISABLED`). Such an opt-in is accident prevention, not a control: `sudo -n` in a leaf is equally available.

### 3.2 Users

- **CP-23.** `invoker` is the user who invoked `sudo` or `doas` (from `SUDO_UID`, or doas's equivalent), checked against the passwd database, when Blokky runs as root. Otherwise it is the current user, and `become: invoker` is a no-op.
- **CP-24.** `become: root` on a node opts it out of `defaults.become`. When Blokky runs as root, `become: root` is a no-op.
- **CP-25.** Becoming the current user is always a no-op; no elevation tool is involved.

### 3.3 Mechanism

- **CP-26.** When the run has root privileges, leaves with another `become` user run with privileges **dropped** to that user; no elevation tool is used.
- **CP-27.** Otherwise the leaf runs through a passwordless elevation tool, `sudo -n -u USER` or `doas -n -u USER`; Blokky never prompts for or forwards passwords. Which tool is used is the implementation's choice (for blokky-cli: configurable, `sudo` first). A tool that needs a password fails the leaf.
- **CP-28.** **Transport.** A `become` leaf gets exactly the argv, environment and script text it would get without `become`, whatever environment policy sudoers or doas.conf set, and none of it appears on a command line visible to other users. How this is done is the implementation's business (for blokky-cli: a `blokky __exec` trampoline, *provisional — verify in spike*).
- **CP-29.** **Files.** A `become` node's own `tempdir` is created by the target user (mode 0700). Capture files stay owned by the run's user. Files the run owns and ancestor tempdirs stay unreadable to the target user: using one as the cwd of a `become` node is a plan error where it can be detected statically, and a run-time error otherwise. File modes are never relaxed; later versions may extend access (ACLs, ownership) but never loosen modes.
- **CP-30.** Stopping a leaf across a privilege boundary (a non-root run stopping a root leaf) is best effort; timeouts and cancellation may not reach it. *Provisional — verify in spike.*

### 3.4 Running as root

- **CP-32.** When the run has root privileges and the plan has no `defaults.become`, implementations SHOULD warn at run start.

### 3.5 Visibility

- **CP-34.** The effective user of every leaf and probe, whether elevation is used and with which tool, is determined statically, so implementations can show it before a run, and it is part of the run result.

### 3.6 Windows

- **CP-35.** `become` is Unix-only; on Windows a reached `become` that would change the user fails the node (`BK_BECOME_FAILED`). Interactive OS consent (UAC, polkit) is not part of the language 1.0 ([ADR 0014](../adr/0014-remaining-features.md)).
