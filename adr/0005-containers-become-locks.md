# 0005: Containers, `become` and locks (open-question batch 5)

- Status: accepted; the `become` decisions are superseded by [ADR 0017](0017-review-features.md)
- Date: 2026-11-04
- Questions: Q16, Q17, Q-j

## Context and problem statement

The [specification-phase brief](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/design/brief.md) §4 moved the language-level parts of containers (Q16) and `become` (Q17) into the draft batch, together with nested locks (Q-j). All three features are `later`, but the draft spec fixes their value shapes and semantics now, so that adding them never breaks a plan. This ADR records the maintainer's answers. Engine detection, termination inside containers and kills across a privilege boundary stay spike and later questions (Q16b in the brief's numbering, spike #1).

Each question was asked as a multiple choice with a recommendation, on 2026-11-04. The options considered are listed per decision below; the chosen one is marked.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| Q16 existing-container mode | `exec` leaves only; scripts copied in with `<engine> cp`; **drop existing mode** |
| Q16 default mounts | cwd only if under the repo root; nothing by default; **always the cwd, read-write** (maintainer's own answer) |
| Q16 `mounts` shape | **mappings `{ host, path, read_only }`**; docker-style strings |
| Q-j nested locks | **forbid nesting, one lock per node**; sorted multi-lock; allow nesting |
| Q17a `defaults.become` | **a user name or `invoker`**; applies only as root; a literal user, always |
| Q17b root-run lint | **warning**; error; info |
| Q17c `doas` | later; **`sudo` and `doas` from the start**; never |
| Q17d config under root | **root's own, root-owned user config**; the invoking user's config; no user config as root |
| Q17e transport across `become` | **trampoline pipe**; `sudo --preserve-env` with relaxed modes; decide after the spike |

## Decision outcome

Five answers follow the recommendation. The maintainer chose differently for three:

- existing-container mode is dropped;
- the cwd is always mounted, because Blokky can't assume a git repo and users also run plans by hand;
- `doas` is supported alongside `sudo` from the start.

### Q16: containers

**Ephemeral mode only.** The value shape is `container: { image, mounts?, user?, env_pass? }`. Blokky starts the container once for the node, runs each leaf in it with `<engine> exec`, and stops (not removes) it at node end; `clean`/`gc` remove it. `container: { exec: NAME }` (existing mode) is dropped and not reserved; a plan that needs a running container calls `exec: [docker, exec, …]` itself.

**Default mounts.** When `mounts` is not given, the node's effective **cwd is mounted read-write at the same path**, wherever it is; Blokky doesn't assume a git repo. Runtime dirs are always added:

- the run's scripts dir, read-only;
- the node's own `tempdir`, when it has one; it becomes the cwd, so it is the cwd mount.

An explicit `mounts` list replaces the default cwd mount (it doesn't add to it); `mounts: []` mounts only the runtime dirs. A cwd that maps through no mount is an error, as the brief says.

**`mounts` entries** are mappings:

```yaml
container:
  image: mcr.microsoft.com/dotnet/sdk:10.0
  mounts:
    - { host: ./src, path: /src, read_only: true }
    - { host: { var: CACHE_DIR }, path: /root/.nuget }
```

- `host` is a host path, a literal or a whole-value reference; relative paths resolve against the invocation cwd.
- `path` is an absolute container path (literal).
- `read_only` defaults to `false`.
- Mappings avoid the colon ambiguity of `host:path:ro` strings with Windows paths, and they allow a variable as a whole value without string concatenation.

Lint flags mounting the engine socket (`container-privileged`, later).

### Q-j: nested locks

Nesting is **forbidden**. A node with `lock` must not have a descendant (including nodes under `finally` and `services`) with `lock`; this is a static error. Each node takes one lock: `lock: NAME` or `lock: { name, wait }`. A plan that needs two resources uses one combined lock name. Nested `blokky run` processes can't be checked statically: re-taking a lock the parent run holds waits until `wait` (or `timeout`) expires; the spec documents this.

### Q17: `become`

**`defaults.become` and `invoker`.** `become` and `defaults.become` take a user name or the special value `invoker`:

- `invoker` is the user from `SUDO_UID` (or doas's equivalent), checked against passwd, when Blokky runs as root under sudo or doas. Otherwise it is the current user, and `become: invoker` is a no-op.
- `defaults.become` applies to every leaf and probe without its own `become`. `become: root` opts a node back to root.
- So a plan with `defaults.become: invoker` runs unchanged with and without sudo; as root it drops to the invoking user except where marked.

**Root-run lint.** When Blokky runs as root and the plan has no `defaults.become`, a `root-run` warning goes to stderr and the report at run start. `strict: true` raises it to error; config can set its severity like any rule (blokky-cli ADR 0003).

**Elevation tool.** `sudo -n -u USER` and `doas -n -u USER` are both supported from the first `become` milestone; both are passwordless only. A user-only config key chooses the tool; when unset, Blokky detects `sudo`, else `doas`, on PATH. As root, Blokky drops privileges itself and needs neither. `leaves` and the report show the tool, the effective user and the elevation per leaf.

**Config under root.** When euid is 0, the user-level config is root's own: Blokky uses root's passwd home and ignores `XDG_CONFIG_HOME`/`HOME` (an exception to blokky-cli ADR 0003, Q-d). The file must be root-owned and not group- or world-writable, otherwise it is a config error. The invoking user's config is not read. Repo configs still apply; they hold free keys only.

**Transport across `become`.** A `become` leaf runs as `<tool> -n -u USER <abs blokky> __exec`. The trampoline reads argv, env and the script text from an inherited pipe:

- nothing sensitive appears on argv or in `ps`;
- it works whatever env policy sudoers or doas.conf set;
- a `become` node's own `tempdir` is created by the target user (0700);
- captured output flows back through the Blokky parent, which stays the owner of capture files;
- ancestor tempdirs and the run dir stay unreadable to the target user; using one as the cwd of a `become` node is a static error where it can be detected, and a runtime error otherwise.

File modes are never relaxed (brief §3.6). The mechanism is confirmed or revised by the spike, together with killing across a privilege boundary.

**Windows:** `become` stays Unix-only until out-of-band consent (§3.7, later) exists.

### Consequences

- Good: the container and `become` shapes in the draft spec are complete, so the reserved keywords can be implemented later without breaking plans.
- Good: one plan file works with and without sudo (`defaults.become: invoker`).
- Good: no secrets on argv, and no relaxed file modes, for leaves running as another user.
- Neutral: dropping existing mode keeps Blokky out of containers it doesn't own; such plans call the engine CLI directly.
- Bad: mounting the cwd read-write by default also mounts `$HOME` or `/` when the plan is run from there. The spec documents it, and a lint rule for broad mounts can be considered.
- Bad: supporting `doas` from the start doubles the elevation paths the spike must verify.
- Bad: forbidding nested locks means combined lock names for multi-resource plans.

## More information

- Brief: §3.1 (modifier table), §3.6 (containers and privilege), §3.8 (locks), §4 (questions).
- Tracker: T-0012; the answers are linked from the [open-questions table](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/plan/TRACKER.md#open-questions).
- Spec files that apply these answers: `spec/containers.md`, `spec/reference.md` (shapes, validity matrix), `spec/syntax.md` (per-field table: `mounts`, `become`, `lock`).
- blokky-cli docs: `docs/configuration.md` (the elevation-tool key, which is user-only, and the root config rule); the lint rule reference (`root-run`).
