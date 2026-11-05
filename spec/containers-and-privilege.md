# Containers and privilege

Status: **draft** (spec 0.1, not yet finalized). Milestone: ***later*** for `container` and `become`; the path model in §1 applies in v0.1.

This document is normative for the language-level behaviour of the `container` and `become` modifiers: value shapes, the path model, mounts, users, scoping and interactions. Their keywords are reserved in v0.1, and a v0.1 implementation rejects them with "not supported in this version". Engine detection, termination inside containers and killing across a privilege boundary depend on spikes and are specified in the blokky-cli design notes; statements marked *provisional — verify in spike* depend on spike results. Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions). Rules carry IDs (`CP-n`).

Decisions: [ADR 0005](../adr/0005-containers-become-locks.md), [ADR 0012](../adr/0012-container-details.md).

## 1. Path model (v0.1)

- **CP-1.** `path:` subjects, `for: { glob }`, `tempdir`, `cwd`, `capture_file`, `stdin: { file }` and `mounts[].host` are **host** paths, evaluated by Blokky on the host, in every milestone.
- **CP-2.** Under `container`, only processes run inside the container: leaves, probes and services. A `path:` condition on a container node still checks the host; the `path-on-container` lint rule warns.

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
- **CP-5.** At node end (after `finally`), the container is **stopped, not removed**, so it can be inspected. It is labelled with the run id and registered as an artefact; `blokky clean` and `gc` remove it.
- **CP-6.** The report records the engine, the image digest and the container id. `leaves` lists the engine commands Blokky will issue as `derived` units, rendered by the single invocation builder.
- **CP-7.** The engine CLI is started with Blokky's own environment, not the node's `env`, so a node can't redirect it (for example with `DOCKER_HOST`). Which engines are supported and how one is chosen is a later question (Q16b).
- **CP-8.** Terminating a leaf inside a container uses an in-container process group with a recorded PID: TERM, grace period, KILL through `<engine> exec … kill`, and stopping the container as the fallback. *Provisional — verify in spike*, including images without a shell or `kill`.

### 2.3 Mounts

- **CP-9.** **Default mount.** When `mounts` is not given, the node's effective **cwd is mounted read-write at the same path**, wherever it is; Blokky doesn't assume a git repository.
- **CP-10.** **Path mapping.** "The same path" means the host path on Linux and macOS. On a Windows host with a Linux container, a host path `C:\src\app` maps to `/c/src/app` (lowercase drive letter, forward slashes); with a Windows container it stays as it is. The same mapping applies to the container-side defaults of `{ var }` host paths.
- **CP-11.** **Runtime mounts** are always added: the run's scripts dir, read-only, at a fixed container path; and the node's own `tempdir`, read-write, when the node has one (it is the cwd, so it is the cwd mount). How the trampoline binary becomes available in the container is *provisional — verify in spike*.
- **CP-12.** **Explicit mounts.** A `mounts` list replaces the default cwd mount; it doesn't add to it. `mounts: []` mounts only the runtime dirs.
- **CP-13.** Each entry is `{ host, path, read_only }`: `host` is a host path (literal or `{ var: X }`), relative paths resolve against the **invocation** cwd; `path` is an absolute container path (literal); `read_only` defaults to `false`.
- **CP-14.** **The container cwd** is the container path the node's effective cwd maps to through the mounts. A cwd that maps through no mount is an error ("add a mount for … or set `cwd` to a container path"). An absolute `cwd` that isn't a host path under a mount is taken as a container path.

### 2.4 Inside the container

- **CP-15.** `exec` argv[0] resolves **inside** the container (the engine's lookup), not on the host. `script` leaves need their shell in the image; the script file is read from the read-only scripts mount.
- **CP-16.** A container process's environment is the image's environment, plus the scoped `env` and `export` mappings of the node and its ancestors, plus the `env_pass` names (taken from Blokky's environment), plus `BLOKKY_RUN_ID` and `BLOKKY_MAX_DURATION`. The host environment is not passed otherwise.
- **CP-17.** **User.** Without `user`, processes run as the image's default user, as with `docker run`. On a rootful engine, running as root with a read-write mount creates root-owned files on the host; the `container-root-write` lint rule warns.
- **CP-18.** Probes on a container node run inside the container (they are processes). `when` is evaluated in the parent's scope, outside the container.

### 2.5 Nesting

- **CP-19.** A node inside a `container` node runs in that container. A `container` on a node inside another container's scope is a plan error.
- **CP-20.** `become` and `container` don't combine: `become` on a node inside a container's scope, or `container` inside a `become` scope, is a plan error. Use `container.user` instead.

### 2.6 Security

Containers are not a sandbox by default. Mounting the engine socket, adding capabilities or running privileged is equivalent to host root; the `container-privileged` lint rule flags engine-socket mounts. The default read-write cwd mount gives the container the same access to the workspace as a host leaf. Blokky never uses a container to decide what is allowed.

## 3. `become`

### 3.1 Shape

```yaml
blokky: 0.1
defaults:
  become: invoker               # as root: drop to the sudo/doas caller
do:
  - exec: [make, build]         # runs as the invoking user
  - name: install
    become: root
    exec: [make, install]
```

- **CP-21.** `become: USER`, `become: invoker` or `become: { user: USER }` (literal). `defaults.become` takes the same values and applies to every leaf and probe without its own `become`.
- **CP-22.** `become` is enabled only by a **user-only** config switch; without it, a plan using `become` fails before it runs, with a message naming the switch. It is an accident-prevention and reviewability opt-in: `sudo -n` in a leaf is equally available.

### 3.2 Users

- **CP-23.** `invoker` is the user who invoked `sudo` or `doas` (from `SUDO_UID`, or doas's equivalent), checked against the passwd database, when Blokky runs as root. Otherwise it is the current user, and `become: invoker` is a no-op.
- **CP-24.** `become: root` on a node opts it out of `defaults.become`. When Blokky runs as root, `become: root` is a no-op.
- **CP-25.** Becoming the current user is always a no-op; no elevation tool is involved.

### 3.3 Mechanism

- **CP-26.** When Blokky runs as root, it **drops privileges** itself for leaves with another `become` user; no elevation tool is used.
- **CP-27.** Otherwise it runs the leaf through `sudo -n -u USER` or `doas -n -u USER` (passwordless only; Blokky never prompts or forwards passwords). A user-only config key chooses the tool; when unset, Blokky uses `sudo` if it resolves on `PATH`, else `doas`. A tool that needs a password fails the leaf.
- **CP-28.** **Transport.** The leaf is started as `<tool> -n -u USER <absolute blokky> __exec`; the trampoline reads argv, the environment and the script text from an inherited pipe. Nothing sensitive appears on a command line, and the sudoers or doas.conf environment policy doesn't matter. *Provisional — verify in spike*, including tools that close extra file descriptors.
- **CP-29.** **Files.** A `become` node's own `tempdir` is created by the target user (mode 0700). Captured output flows back through the Blokky parent, which stays the owner of capture files. The run dir and ancestor tempdirs stay unreadable to the target user: using one as the cwd of a `become` node is a plan error where it can be detected statically, and a run-time error otherwise. File modes are never relaxed; later versions may extend access (ACLs, ownership) but never loosen modes.
- **CP-30.** Killing a leaf across a privilege boundary (a non-root Blokky stopping a root leaf) is not guaranteed. *Provisional — verify in spike*, for both `sudo` and `doas`.

### 3.4 Running as root

- **CP-31.** When Blokky runs with euid 0, the user-level config is root's own: Blokky uses root's passwd home and ignores `XDG_CONFIG_HOME`/`HOME`. The file MUST be root-owned and not group- or world-writable, else it is a config error. The invoking user's config is not read; repo configs still apply.
- **CP-32.** When Blokky runs as root and the plan has no `defaults.become`, the `root-run` lint rule warns at run start (raised to `error` by `strict`).
- **CP-33.** Strict mode flags raw `sudo`, `doas`, `su`, `pkexec` and `runas` in leaves (`raw-privilege-escalation`).

### 3.5 Visibility

- **CP-34.** `leaves`, `blokky plan` and the report show, per leaf and probe, the effective user, whether elevation is used and with which tool.

### 3.6 Windows

- **CP-35.** `become` is Unix-only until out-of-band consent (*later*, Q18) exists; on Windows a reached `become` that would change the user fails the node.

## 4. Agent handoff pattern (works in v0.1)

Without `become`, an agent can still prepare work that needs root, and the user runs it:

1. The agent writes the plan to a `*.blokky.yaml` file.
2. The user reviews it (`blokky plan`, `blokky leaves`) and notes the printed SHA-256.
3. The user runs it: `sudo blokky run --expect-sha256 <hash> [--input NAME=VALUE …] file.blokky.yaml`. The hash covers the plan; the reviewed input values are visible in `blokky plan --input …` and recorded in the report.

Any password prompt happens in the user's terminal, before Blokky starts.
