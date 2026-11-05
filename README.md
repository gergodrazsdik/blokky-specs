# Blokky language specification

Blokky is a small, declarative YAML block language and runner that wraps shell commands in common structured-programming blocks: timeouts, retries, polling loops, parallel groups, temp directories and cleanup. Its main users are coding agents (Claude Code, Codex and others), and secondarily the humans who review what those agents run. Control flow and resource lifetime move into a reviewable declarative layer, the leaf commands stay simple and single-purpose, and the runtime owns and cleans up its own artefacts. Blokky is not a sandbox: it makes what will run visible and easy to validate, and never does more than the equivalent bash script could.

> **Status: pre-alpha, specification phase. There is nothing to install yet.** Every spec document is still a placeholder or a draft.

## Two repositories

| Repo | Contents |
|---|---|
| **blokky-specs** (this repo) | The language specification, normative JSON contracts and schemas, examples, and the conformance suite (cases, format, testkit interface). |
| [blokky-cli](https://github.com/gergodrazsdik/blokky-cli) | The .NET implementation (CLI host, later an MCP host), configuration, validation and hook integration, threat model, agent docs, install, design docs and CI/CD. |

A change that touches both repos gets two linked pull requests; the spec PR merges first. blokky-cli's CI runs this repo's conformance suite, checked out at a pinned tag, against its binary.

## Spec index

| Document | Contents |
|---|---|
| [spec/overview.md](spec/overview.md) | Concepts, mental model, when (not) to use Blokky |
| [spec/syntax.md](spec/syntax.md) | YAML surface rules, root document, plan inputs, per-field table, pitfalls |
| [spec/reference.md](spec/reference.md) | Every node kind and modifier, milestone-tagged; validity matrix |
| [spec/execution-model.md](spec/execution-model.md) | Modifier order, start order, cancellation, status propagation |
| [spec/variables.md](spec/variables.md) | Names, inputs, captures, scope, outputs, secrets |
| [spec/conditions.md](spec/conditions.md) | Subjects, operators, composites, probes |
| [spec/shells.md](spec/shells.md) | `exec` splitting, per-shell invocation, OS matrix |
| [spec/containers-and-privilege.md](spec/containers-and-privilege.md) | `container` and `become` (later milestone) |
| [spec/errors.md](spec/errors.md) | The language's `BK_` error codes |
| [spec/results.md](spec/results.md) | The abstract run result that conformance cases assert on |
| [spec/glossary.md](spec/glossary.md), [spec/prior-art.md](spec/prior-art.md) | Terms; related tools |
| [schema/](schema/) | The plan JSON Schema (normative for structure) |
| [examples/](examples/README.md) | Runnable example plans |
| [conformance/](conformance/README.md) | Conformance suite format and testkit interface |
| [adr/](adr/README.md) | Language decision records |

## Versioning

- The specification has its **own semantic version**, independent of blokky-cli. A plan's `blokky:` field names the spec version it targets (the exact scheme is open question Q13).
- Each blokky-cli release declares which spec versions it supports.
- The plan schema's `$id` is versioned per spec release. The JSON formats of the reference implementation (report, events, `leaves`, validator protocol) are specified in [blokky-cli `docs/contracts/`](https://github.com/gergodrazsdik/blokky-cli/tree/main/docs/contracts).
- Unknown keys in a plan are errors, so an older binary fails clearly on a newer plan.
- **Everything may change until 1.0.** The spec and the tool stay 0.x until the plan format is frozen. Features are tagged `v0.1` or `later`; `later` keywords are already reserved so they can be added without breaking plans.
- Releases are signed, annotated `vX.Y.Z` tags; [CHANGELOG.md](CHANGELOG.md) lists them.

## Where to look

- [ROADMAP.md](ROADMAP.md): language features by milestone.
- [Work tracker](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/plan/TRACKER.md) (in blokky-cli, shared by both repos).
- [Design brief](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/design/brief.md) driving the current phase.
- [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Contributions are accepted under the [Developer Certificate of Origin](https://developercertificate.org/) (no CLA). The spec text, schemas, examples and conformance cases are all under Apache-2.0 ([ADR 0006](adr/0006-shims-and-license.md)).
