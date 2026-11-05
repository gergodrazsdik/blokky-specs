# Agent instructions: blokky-specs

These instructions are for coding agents (Claude Code, Codex and others) working in this repo. Humans: see [CONTRIBUTING.md](CONTRIBUTING.md).

## This repo

blokky-specs holds the Blokky **language specification**: spec documents (`spec/`), normative JSON Schemas (`schema/`), examples (`examples/`), the conformance suite (`conformance/`: case format, testkit interface, cases) and language ADRs (`adr/`). It is versioned on its own; a plan's `blokky:` field names a spec version. Its sibling **blokky-cli** holds the .NET implementation, configuration, validation, threat model, agent docs, design docs, CI/CD and the shared work tracker. Expect both repos checked out side by side (`../blokky-cli`). Each has its own branches, PRs, ADRs and CHANGELOG. A change touching both gets two linked PRs; **the spec PR merges first**.

## Brief and process

The design brief is in blokky-cli: `../blokky-cli/docs/design/brief.md` when both repos are checked out side by side ([on GitHub](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/design/brief.md)). It is the source of truth for the current phase. Read it before any non-trivial work. Its §4 open questions are asked, not decided silently; its §8 defines the process.

**Current phase: specification.** No implementation code. Spike code is allowed only on unmerged `spikes/*` branches in blokky-cli, after the maintainer approves the spike plan.

Shared files in this repo are owned by the main agent; subagents propose changes to them in their PR description: `spec/glossary.md`, `schema/blokky.schema.json`, `spec/errors.md`, `adr/README.md`.

## Working agreement

- Work on feature branches (`docs/<topic>`). **Never commit to `main`.**
- Push branches and open PRs with `gh`. The PR description gives a summary, the decisions it applies (link ADRs), tracker IDs and open items. Draft-spec PRs are marked **Draft spec**. **Never merge PRs**; the maintainer reviews and merges.
- Conventional Commits (`docs(spec): …`, `chore: …`); small, logical commits.
- **DCO and signatures:** always `git commit -s`, with commit signing enabled; never disable signing or pass `--no-verify`. Tags are annotated and signed (`git tag -s`), and release tags are the maintainer's. Write the commit message to a file outside the repo and pass it with `git commit -s -F <file>`.
- After a PR merges, rebase remaining branches onto `main`.

## Commands

Use `just` (`just --list`):

| Recipe | What it does |
|---|---|
| `just doctor` | Check tools and git settings; prints install hints. |
| `just hooks` | Install the lefthook git hooks. |
| `just lint` | All linters: `lint-md`, `lint-yaml`, `lint-actions`, `lint-sh`, `typos`, `editorconfig`. |
| `just pin` | Pin workflow actions to full SHAs (`pinact run`). |
| `just claude` | Start Claude Code with `../blokky-cli` added. |

Run `just lint` before committing. The hooks (pre-commit, commit-msg) run the same checks on staged files plus gitleaks, the DCO sign-off and the Conventional Commits header.

## Work tracker

The single tracker for both repos is in blokky-cli: `../blokky-cli/docs/plan/TRACKER.md`. Rules:

- IDs are never reused: `T-NNNN` tasks, `F-NNNN` findings, and the brief's own question IDs (`Q1…`, `Q-a…`).
- Every task has a repo tag: `[cli]`, `[specs]` or `[both]`.
- Finished items stay in place, ticked, with date and commit/PR link. Dropped items (`[-]`) keep a one-line reason.
- Update the tracker **in the same PR** as the work it tracks. For work in this repo, that means a companion blokky-cli PR (linked from this one), or a note in this PR's description for the maintainer.
- Start from "Now", in phase order. Propose before starting anything larger than one PR. Ask the maintainer about `[!]` items.
- New questions and findings discovered during work are added immediately, never only mentioned in chat.
- When a phase completes, add a one-line summary under its heading.

## Writing style

- Precise and concise. No marketing fluff.
- Normative language (MUST/SHOULD/MAY, RFC 2119) in the spec.
- Every example must be something a user could actually run once an implementation supports its features; examples and sketches use canonical forms only.
- The spec describes the whole language 1.0 without milestone tags; [ROADMAP.md](ROADMAP.md) lists every feature.

## Security posture (don't over-engineer)

- The baseline is "the same as plain bash": what an agent could do with a plain shell tool call. Blokky must never be *less* safe than that and should be more reviewable.
- It must not grant capabilities, bypass the runner's permission system, or hide what will run.
- Blokky is not a sandbox. Agents keep a generic shell tool; controls that only work if agents can *only* use Blokky are out of scope.
- Hygiene (strict lint, secret masking, display sanitization) is not a control; the runner's permissions, the hook and the validator are. The spec must not present hygiene as enforcement.
- Resource bounds exist for ergonomics and predictability, not as security boundaries.

## Local overrides

`local.just`, `CLAUDE.local.md`, `.claude/settings.local.json` and `lefthook-local.yml` are personal and gitignored. Never commit them, and never put machine-specific paths or tools into committed files.
