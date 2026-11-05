# 0011: PowerShell prologue placement (draft round 5)

- Status: accepted
- Date: 2026-11-05
- Questions: none from the brief's §4 list; left open by ADR 0003 (consequences) and raised while drafting `spec/shells.md` (T-0020)

## Context and problem statement

ADR 0003 gives PowerShell `script` leaves the prologue `$ErrorActionPreference = 'Stop'`, so cmdlet errors end the script instead of being lost. Unlike bash's `-o pipefail`, PowerShell has no command-line option for it, so the prologue must go into the script text. `using` statements and a `param()` block must come first in a PowerShell script, and line numbers in error messages should still match the plan. ADR 0003 left the placement to `shells.md`.

## Considered options

1. **Prefix the first statement line:** insert `$ErrorActionPreference = 'Stop';` (followed by a space) at the start of the first line that isn't blank, a comment or a `using` statement; a `param(` block there is a plan error.
2. A wrapper script that sets the preference and invokes the user's file with `& <file>; exit $LASTEXITCODE`.
3. The prologue on its own line, after leading `using` lines.

## Decision outcome

Chosen option: "prefix the first statement line", because it keeps every line number exact, leaves `using` statements valid, needs one file and keeps the plain `-File` exit-code path. Plan scripts receive no arguments, so a `param()` block has no use and rejecting it costs nothing. `#Requires` may appear anywhere in a script and is unaffected.

### Consequences

- Good: error messages point at the plan's own line numbers.
- Good: `leaves` shows the exact text that runs, prologue included.
- Neutral: Blokky needs a small line scanner (blank, comment, `using`) for PowerShell scripts; block comments (`<# … #>`) at the top count as comments.
- Bad: a script that starts with `param(` must be rewritten.

## More information

- Applied in: `spec/shells.md` SH-17.
- Tracker: T-0020.
