# Shells and leaf execution

Status: **draft** (spec 0.1, not yet finalized)

This document is normative for how leaves become processes: splitting `exec` strings, building Windows command lines, writing and invoking `script` files per shell, choosing a shell, resolving executables, the shell × OS matrix, and the injection properties of each shell. Process lifecycle (sessions, kills, completion) is in [execution-model.md](execution-model.md). Normative keywords are used as defined in [syntax.md §1](syntax.md#1-conventions). Rules carry IDs (`SH-n`) for conformance cases.

## 1. `exec`

### 1.1 Array form

- **SH-1.** `exec: [prog, arg, { var: X }]` gives argv directly: each element is exactly one argument, with no splitting, quoting or expansion. Element 0 MUST be a literal; a `{ var: X }` element is replaced by the variable's value as one argument (an empty value is an empty argument).

### 1.2 String form

`exec: dotnet build -c Release` is a shorthand for static commands. Blokky splits the string into argv with these rules:

- **SH-2.** Words are separated by unquoted spaces, tabs and newlines. Leading and trailing whitespace is ignored.
- **SH-3.** Inside single quotes, every character is literal, until the next single quote.
- **SH-4.** Inside double quotes, characters are literal except `\"` (a quote) and `\\` (a backslash); any other backslash is literal.
- **SH-5.** Outside quotes, a backslash makes the next character literal.
- **SH-6.** Adjacent quoted and unquoted parts join into one word (`--name='a b'` is one argument `--name=a b`). `''` or `""` alone is an empty argument.
- **SH-7.** There is **no expansion, globbing or operator** of any kind. These are plan errors, each pointing to the array form with `{ var: X }` or to `script`:
  - unquoted `|`, `&`, `;`, `<`, `>`, `(`, `)`, `*`, `?`, `[`, `]`, `{`, `}`, and `~` or `#` at the start of a word;
  - `$` or a backtick outside single quotes;
  - an unterminated quote, or a string with no words.
- **SH-8.** `blokky plan` and `leaves` show the resulting argv.

### 1.3 Windows command lines

- **SH-9.** On Windows a program receives one command line, not an argv array. Blokky builds it from argv with the quoting that `CommandLineToArgvW` and the C runtime parse back to the same argv (what .NET `ProcessStartInfo.ArgumentList` produces). Programs that parse their command line differently (for example `msiexec`) may see different arguments; the docs say so.
- **SH-10.** A program resolving to a `.bat` or `.cmd` file is an error: cmd.exe would re-parse the arguments with its own rules. The message suggests running such tools (`npm`, `npx`) in a PowerShell `script`.

## 2. `script`

### 2.1 Script file

- **SH-11.** The script text is written to a file in the run dir, `scripts/<node-file-name>.<ext>`, with mode 0600, before the leaf starts. `<node-file-name>` is derived from the node's path id; it is never derived from `name`. The extension is `.sh` for `bash` and `sh` and `.ps1` for `pwsh` and `powershell`.
- **SH-12.** The file holds the text as written (YAML block scalars give LF line endings), encoded as UTF-8 without a BOM, except for `powershell` (Windows PowerShell 5.1), which gets a UTF-8 BOM so it reads non-ASCII text correctly.
- **SH-13.** The file is passed to the shell **as a file**, never with `-c`: there are no command-line length limits, no quoting layer, and the exact script stays inspectable until `clean`. Consequences: `$0` (POSIX) and `$PSCommandPath` (PowerShell) are the script file's path, and shell error messages name that file.
- **SH-14.** The text never interpolates `${…}`. Plan variables reach it only through `env:` and `export:` as environment variables.

### 2.2 Invocation table

([ADR 0003](../adr/0003-execution-defaults.md))

| Shell | Invocation | Error handling |
|---|---|---|
| `bash` | `<bash> --noprofile --norc -o pipefail <file>` | `pipefail`; no `-e`, no `-u` |
| `sh` | `<sh> <file>` | none |
| `pwsh` | `<pwsh> -NoProfile -NonInteractive -File <file>` | prologue `$ErrorActionPreference = 'Stop'` |
| `powershell` | `<powershell> -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <file>` | prologue `$ErrorActionPreference = 'Stop'` |
| `zsh` (*later*) | defined when added | |
| `fish` (*later*) | defined when added | |

`<bash>` etc. are absolute paths (§4).

- **SH-15.** `sh` gets no options: common `/bin/sh` implementations (dash) reject `--noprofile`/`--norc`, and a non-interactive `sh` reads no startup file once `ENV` is cleared.
- **SH-16.** In bash, `pipefail` is set with the `-o pipefail` option, so the script text is unchanged and line numbers match the plan. A failing command in the middle of a bash or sh script doesn't stop it; the script's exit status is the leaf's.
- **SH-17.** **PowerShell prologue.** Blokky inserts `$ErrorActionPreference = 'Stop';` (followed by a space) at the start of the first line of the script that isn't blank, a comment, or a `using` statement. The prologue shares that line, so line numbers in error messages stay exact ([ADR 0011](../adr/0011-pwsh-prologue.md)). A `param(` block at that position is a plan error (plan scripts receive no arguments). With the prologue, a cmdlet error ends the script with exit code 1 instead of being written to stderr while the script exits 0.
- **SH-18.** `$PSNativeCommandUseErrorActionPreference` is not set: a failing native program doesn't stop a PowerShell script, matching "no `-e`" in bash.
- **SH-19.** The exact invocation, including the prologue, is shown in `leaves` and `blokky plan`.
- **SH-20.** The exit code of `pwsh -File` and `powershell -File` for a script that ends without `exit` after a failing native command is *provisional — verify in spike*; the spec will state it.

### 2.3 Choosing the shell

- **SH-21.** A `script` leaf's (or script probe's) shell is, in order: its own `shell:`, `defaults.shell`, the config key `shell`, then detection.
- **SH-22.** **Detection** is fixed and deterministic: on Unix, `bash` if it resolves on `PATH`, else `sh` (`$SHELL` is never consulted); on Windows, `pwsh`, else `powershell`. `blokky plan` shows the result.
- **SH-23.** A reached `script` whose shell isn't supported on the current OS (§5), or can't be resolved, fails the node. Statically false `host:` branches are pruned before this check, so portable plans work.

## 3. A leaf's environment

- **SH-24.** A leaf's environment is built as in [variables.md §7](variables.md#7-environment): Blokky's environment, the scoped `env`/`export` mappings, `BLOKKY_RUN_ID` and `BLOKKY_MAX_DURATION`; then `BASH_ENV` and `ENV` are removed, so no shell reads a startup file through them.

## 4. Executable resolution

- **SH-25.** Resolution uses **Blokky's own** `PATH`, never a node's `env`, and never the current directory or Blokky's own directory.
- **SH-26.** An argv[0] that contains a path separator (`./tools/gen`, `C:\tools\gen.exe`) is a path, resolved against the node's cwd if relative; it is not looked up on `PATH`.
- **SH-27.** On Windows, a name without an extension is tried with `.com` and `.exe` only, in that order; the `PATHEXT` variable is ignored. `.bat` and `.cmd` are never run directly (SH-10).
- **SH-28.** Shell binaries resolve the same way, unless the user-only config key `shells.<name>.path` gives an absolute path. On Windows, `bash` and `sh` resolve **only** through that key (Git Bash or MSYS), never through `PATH`, which could find `C:\Windows\System32\bash.exe`, the WSL launcher ([ADR 0003](../adr/0003-execution-defaults.md)).
- **SH-29.** The launcher receives the resolved absolute path, so platform search orders don't apply (*provisional — verify in spike*). The resolved path appears in `leaves`, `blokky plan` and the report.

## 5. Shell × OS matrix

| Shell | Linux | macOS | Windows |
|---|---|---|---|
| `bash` | ✓ | ✓ | only via `shells.bash.path` (Git Bash, MSYS) |
| `sh` | ✓ | ✓ | only via `shells.sh.path` |
| `pwsh` | ✓ | ✓ | ✓ |
| `powershell` | — | — | ✓ |
| `zsh` (*later*) | ✓ | ✓ | — |
| `fish` (*later*) | ✓ | ✓ | — |
| `cmd` | not supported | | |

`cmd` is not supported on any OS: cmd.exe expands `%X%` textually before parsing every command, so passing values through the environment would degrade to text substitution.

## 6. Injection properties

These describe how values that reach a shell through the environment can still change what runs. They are documented hygiene; lint rules flag the common mistakes. None of them is a control ([reference.md §9](reference.md#9-security-considerations)).

- **POSIX shells.** An unquoted `$X` is split into words and globbed, so a value can inject extra arguments or file names. Write `"$X"`. The `posix-unquoted-var` lint rule flags unquoted expansions of exported names.
- **PowerShell variables.** An exported plan variable is an environment variable: write `$env:X`, not `$X` or `${X}` (which refer to PowerShell variables and are empty). The `pwsh-env-var-syntax` lint rule flags it.
- **PowerShell argument passing.** PowerShell 7.3 and later pass arguments to native programs as given (`$PSNativeCommandArgumentPassing`); Windows PowerShell 5.1 re-quotes them and mishandles empty strings and embedded double quotes. Prefer `exec` for native programs with variable arguments.
- **`.cmd` shims from PowerShell.** `npm`, `npx`, `pnpm`, `yarn` and other `.cmd`/`.bat` files re-parse their arguments in cmd.exe, so a variable argument is exposed to `%X%` expansion and cmd metacharacters. The `pwsh-cmd-shim-args` lint rule flags it; the safe alternative is an `exec` leaf that runs the package's JavaScript entry point with `node` ([ADR 0006](../adr/0006-shims-and-license.md)).
- **Argument injection.** A value starting with `-` is read as an option by most programs. Put `--` before item values, captures and inputs passed as arguments, where the program supports it (the `argument-injection-dashdash` lint hint).
- **Dynamic code.** Running a variable as code (`eval`, `source`, `.`, `sh -c "$X"`, `iex`, `Invoke-Expression`, a variable in command position) is flagged `dynamic_exec` in `leaves` (§7).

## 7. Script analysis

- **SH-30.** In v0.1, Blokky analyses `script` text with **token-level heuristics** for POSIX shells and PowerShell. They drive the script-hygiene lint rules and set the `dynamic_exec` flag on a unit when the text contains:
  - a variable expansion in command position;
  - `eval`, `source`, `.` (as a command), or `sh`/`bash -c` with an expansion;
  - `iex` or `Invoke-Expression`;
  - an expansion piped into a known interpreter (`sh`, `bash`, `python`, `node`, `pwsh`, …).
- **SH-31.** The heuristics may miss constructs; a missed case is a lint false negative, not a security failure, because `script` units are never auto-allowed by rules mode and validators see the full text. A hand-written POSIX lexer is planned after v0.1.
- **SH-32.** Execution never switches between `exec` and `script` automatically. *Later*, a lint hint may suggest `exec` for scripts that use no shell features.
