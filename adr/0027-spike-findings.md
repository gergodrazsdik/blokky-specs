# 0027: Findings from the MVP spikes

- Status: accepted
- Date: 2026-11-07
- Questions: none from the brief; the spec items of the MVP spike findings (tracker T-0030).

## Context and problem statement

The MVP spikes in blokky-cli ([cli ADR 0007](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/adr/0007-runtime-plan.md), the runtime plan) checked the runtime behaviour the spec relies on: process launch and tree stop, executable resolution, run-owned file removal, the YAML front end, the regex subset on .NET, `pwsh` exit codes and the prologue scanner, and how editors validate plans against the schema. They confirmed the rules marked *provisional — verify in spike* (except for Windows) and found points the spec left open or got wrong. The maintainer decided them on 2026-11-07; the decision record is [docs/review/spikes-mvp.md](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/review/spikes-mvp.md) in blokky-cli. This ADR applies its spec items.

## Considered options

| Item | Options (chosen in bold) |
|---|---|
| T-1 colour codes in captured output | **(a) `NO_COLOR=1` for every leaf, and `TERM=dumb` when the run's environment has no `TERM`; the plan's `env` can override both**; (b) `TERM=dumb` for `pwsh` leaves only; (c) nothing, plans set them |
| The `pwsh` minimum | **7.4 or later**; 7.2 or later |
| Regex size | **bounded in the spec**; left to each engine |
| The batch | **accepted as proposed** |

## Decision outcome

- **Provisional markers.** EM-22, EM-68 and SH-29 are no longer provisional: the Linux spikes confirmed them. In EM-68 step 3, "stopped" means that no live process of the leaf's OS grouping is left, not that signals were sent.
- **Executable resolution.** Empty and relative `PATH` entries are skipped, since both name the current directory (SH-25). A relative argv[0] path is joined to the cwd as written: `..` is resolved by the OS, not collapsed lexically (SH-26). The process's argv[0] is the name as found in the plan: argv[0] as written for `exec`, the resolved shell path for `script` (SH-29).
- **Spawn failures.** `BK_SPAWN_FAILED` with `bad_format` covers every file the OS can't execute (on Unix `ENOEXEC`, such as a script without a shebang line); Blokky never retries it through `/bin/sh` (errors.md §5.1, SH-29).
- **Run-owned files.** A removal stopped by a mount point keeps the mount point and its ancestors, doesn't fail the node, and is reported as partial in the run result's `warnings`, with the kept path (EM-69, results.md §2, reference.md §4.5). A run-level warning is the smallest place that needs no new result field.
- **Plan text.**
  - U+2028 and U+2029 are rejected by the character lint: YAML 1.1 parsers and some editors treat them as line breaks, so tools would read the plan differently (SY-12).
  - `detail.offset` of invalid UTF-8 counts from the first raw byte, a BOM included (SY-7).
  - An empty key (`: a`) is a rejected key, like a complex key (SY-17).
  - An empty sequence item (`-` followed by nothing) is an empty value, located at the `-` (SY-20).
- **Regex.**
  - Repetition counts are at most 1000, and a pattern has at most 10 000 nodes once counted repetitions are expanded; a node is a literal, `.`, class, class escape, anchor or boundary, counted once per copy. A pattern over the bound is outside the subset (RF-22). Without a bound, the engine's own size cap (10 000 automaton nodes for .NET's `NonBacktracking`, RE2's program size) would decide validity per implementation (new SY-104, SY-61, RF-22).
  - Lexical edges: outside a class a `]` or `}` that closes nothing is itself; `-` in a class is literal first or last; `\f` and `\v` (FF, VT) are escapes; the escapes allowed inside a class are listed (SY-61).
  - `(?i)` doesn't change `\w`, `\d`, `\s` and their negations, which stay ASCII; a class is case-folded before it is negated (SY-61).
  - CO-12's simple uppercase mapping is pinned to Unicode 16.0, because platform case-insensitive APIs differ (U+0131, U+017F, U+212A, the final sigma) and so do Unicode versions (CO-12).
- **PowerShell.**
  - The prologue scanner (SH-17): keywords are matched case-insensitively; when the line closes a block comment, the prologue goes right after its `#>` (at the line start it would be inside the comment and silently lost); a `param` block is detected also when `(` is on a later line or after attributes over several lines; a top-level named block (`begin`, `process`, `end`, `clean`, `dynamicparam`) is a plan error like `param(` (`BK_PLAN_INVALID`, rule SH-17), because plan scripts take no pipeline input; a script with no statement gets no prologue.
  - SH-18 notes the opt-in `$PSNativeCommandUseErrorActionPreference = $true` (7.4 and later).
  - SH-20 is normative: `pwsh` 7.4 or later; a script that ends without `exit` exits 0, whatever `$LASTEXITCODE` is; an uncaught terminating error gives 1; `exit N` gives N mod 256 on Unix. Windows `powershell` 5.1 stays provisional until the Windows spike (0.6).
- **T-1 Colour codes.** pwsh writes ANSI colour codes into redirected stderr when `TERM` looks like a colour terminal; `TERM=dumb` stops it on every version, `NO_COLOR` only on 7.6, and other tools behave alike. Every leaf gets `NO_COLOR=1`, and `TERM=dumb` when the environment the run started with has no `TERM` (a container leaf: when the image's environment has none). They are defaults below the plan's `env` and `export`, unlike `BLOKKY_*`, which come last; neither name is forbidden or reserved (VA-44, VA-39, EM-16, SH-24, CP-16, reference.md §4.7).
- **Editor guidance.**
  - SY-89 has a row for a plain `~` or `null` in a string field: valid, but editors read it as null, so it gets a warning with the fix-it to quote it.
  - SY-95 says that editors validate typed values, so they can't see how a number or boolean was spelled; Blokky's validator is authoritative.
- **Schema.**
  - Input `description` and the regex fields (`matches`, `not_matches`, input `matches`) accept any scalar.
  - Lock names and `tempdir.prefix` also accept non-negative integers, which an unquoted digit string becomes in an editor (new `$defs` `lockName`, `tempdirPrefix`, `regex`).
  - The grammar `$defs` carry a `description` that names the grammar and its rule. `errorMessage` and `patternErrorMessage`, which the spike tested, are VS Code extensions that JSON Schema 2020-12 doesn't define, so the schema uses the standard keyword.
  - Every key of the node, root and input mappings has a one-line `description` for hover and completion. The text is non-normative; reference.md stays normative.

### Consequences

- Good: every provisional marker on Linux behaviour is gone, and the rules say what the spikes measured.
- Good: a pattern within the subset compiles in every implementation, and `ignore_case` gives the same answer on every platform.
- Good: captures of `pwsh` and other leaves no longer contain colour codes by default.
- Neutral: implementations need a Unicode 16.0 case table and must raise or avoid their regex engine's size cap up to the SY-104 bound.
- Neutral: a PowerShell script whose last command is a failing native program exits 0, unlike bash; plans that need that status end with `exit $LASTEXITCODE`.
- Bad: a script starting with a named block must be rewritten, as one starting with `param(` already had to be.

## More information

- Applied in: `spec/execution-model.md`, `spec/shells.md`, `spec/errors.md`, `spec/results.md`, `spec/reference.md`, `spec/syntax.md`, `spec/conditions.md`, `spec/variables.md`, `spec/containers.md`, `conformance/README.md`, `schema/blokky.schema.json`.
- New rule: SY-104.
- Conformance cases to follow (decision record): ı/I, `(?i)[a-z]` against ſ, `\B` on `aéb`, an astral `.`, the regex size bound, the prologue edge cases and the `pwsh` exit codes.
- Companion: [blokky-cli ADR 0008](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/adr/0008-spike-findings.md) (run-control contract, install docs, design defaults).
- Spike reports: `docs/design/notes/spike-*.md` in blokky-cli.
- Tracker: T-0030.
