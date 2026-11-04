# 0006: `.cmd` shims and the spec license (open-question batch 6, language part)

- Status: accepted
- Date: 2026-11-04
- Questions: Q-l, Q-q (spec-text license, testkit split)

## Context and problem statement

Batch 6 of the [specification-phase brief](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/design/brief.md)'s §4 questions covers platform details and the repository split. This ADR records the two answers that concern this repo:

- how `spec/shells.md` treats `.cmd` shims called from PowerShell (Q-l);
- the license of the spec text, plus where the conformance testkit lives (both parts of Q-q).

The process-control launcher (Q-e), Windows agent invocation (Q-h), the heredoc sentinel (Q-o) and the conformance checkout (the rest of Q-q) are in [blokky-cli ADR 0004](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/adr/0004-platform-invocation-conformance.md).

Each question was asked as a multiple choice with a recommendation, on 2026-11-04. The options considered are listed per decision below; the chosen one is marked.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| Q-l `.cmd` shims from pwsh | **lint warning**; document only |
| Q-q spec-text license | **Apache-2.0 for everything**; CC BY 4.0 for prose, Apache-2.0 for code-like files |

## Decision outcome

Both answers follow the recommendation.

### Q-l: `.cmd` shims called from PowerShell

Package-manager shims such as `npm`, `npx`, `pnpm` and `yarn` are `.cmd` files on Windows. When a pwsh or powershell script calls one, cmd.exe re-parses the arguments, so a variable argument is exposed to cmd's `%X%` expansion and metacharacters. (`exec` already rejects `.bat`/`.cmd` targets, brief §3.5.)

- `spec/shells.md` documents the risk and the safe alternative: an `exec` leaf that runs the package's JavaScript entry point with `node`, or literal arguments only.
- A heuristic lint rule, **`pwsh-cmd-shim-args`**, flags a PowerShell script that passes a variable (`$X`, `$env:X`, `${X}`) to a command that is a known shim or that resolves on PATH to a `.cmd`/`.bat` file. Lint resolves PATH without spawning anything. Default severity `warning`; `strict: true` raises it to `error` (the scheme of blokky-cli ADR 0003, Q10).

### Q-q: spec license and testkit split

- **License:** everything in blokky-specs stays **Apache-2.0**, with DCO sign-off and no CLA: spec prose, ADRs, schemas, examples and conformance cases. A single license with a patent grant lets implementers copy spec text and schemas into code and docs without tracking per-path notices.
- **Testkit:** confirmed as in the baseline. The required fake-executable behaviours are specified here (`conformance/testkit-interface.md`); the implementation (`blokky-testkit`) lives in blokky-cli and is never shipped in release archives.
- The repo names `blokky-specs` and `blokky-cli`, chosen at bootstrap, are confirmed (blokky-cli ADR 0001).

### Consequences

- Good: Q-q is fully answered; README's note about a possible CC BY 4.0 switch is removed.
- Good: the shim risk gets a fix-it in the plan, not just a paragraph in the docs.
- Neutral: the rule is a heuristic; a false positive is at most a warning outside strict mode.
- Bad: Apache-2.0 is an unusual license for prose; reusing spec text elsewhere must keep its notice.

## More information

- Brief: §0.1 (repositories), §3.5 (shells, `.cmd` targets), §4 (questions).
- Tracker: T-0013; the answers are linked from the [open-questions table](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/plan/TRACKER.md#open-questions).
- Spec files that apply these answers: `spec/shells.md` (Q-l); `README.md` (license).
- Companion: [blokky-cli ADR 0004](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/adr/0004-platform-invocation-conformance.md) (Q-e, Q-h, Q-o, Q-q checkout).
