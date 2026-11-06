# Shells and leaf execution

Status: **draft** (`1.0.0-draft`, not yet finalized)

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
- **SH-8.** The resulting argv is determined statically, so implementations can show it before a run.

### 1.3 Windows command lines

- **SH-9.** On Windows a program receives one command line, not an argv array. Blokky builds it from argv with the quoting that `CommandLineToArgvW` and the C runtime parse back to the same argv (what .NET `ProcessStartInfo.ArgumentList` produces). Programs that parse their command line differently (for example `msiexec`) may see different arguments; the docs say so.
- **SH-10.** A program resolving to a `.bat` or `.cmd` file is an error: cmd.exe would re-parse the arguments with its own rules. The message suggests running such tools (`npm`, `npx`) in a PowerShell `script`.

## 2. `script`

### 2.1 Script file

- **SH-11.** The script text is written to a file owned by the run (readable only by the run's user) before the leaf starts. Its name is derived from the node's path id, never from `name`. The extension is `.sh` for `bash` and `sh`, `.zsh` for `zsh`, `.fish` for `fish`, and `.ps1` for `pwsh` and `powershell`.
- **SH-12.** The file holds the text as written (YAML block scalars give LF line endings), encoded as UTF-8 without a BOM, except for `powershell` (Windows PowerShell 5.1), which gets a UTF-8 BOM so it reads non-ASCII text correctly.
- **SH-13.** The file is passed to the shell **as a file**, never with `-c`: there are no command-line length limits, no quoting layer, and the exact script stays inspectable until `clean`. Consequences: `$0` (POSIX) and `$PSCommandPath` (PowerShell) are the script file's path, and shell error messages name that file.
- **SH-14.** Blokky never interpolates `${…}` in script text; `${…}` there is the shell's own syntax and reaches the shell unchanged. Plan variables reach the script only through `env:` and `export:` as environment variables.

### 2.2 Invocation table

([ADR 0003](../adr/0003-execution-defaults.md))

| Shell | Invocation | Error handling |
|---|---|---|
| `bash` | `<bash> --noprofile --norc -o pipefail <file>` | `pipefail`; no `-e`, no `-u` |
| `sh` | `<sh> <file>` | none |
| `pwsh` | `<pwsh> -NoProfile -NonInteractive -File <file>` | prologue `$ErrorActionPreference = 'Stop'` |
| `powershell` | `<powershell> -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <file>` | prologue `$ErrorActionPreference = 'Stop'` |
| `zsh` | `<zsh> --no-rcs -o pipefail <file>` | `pipefail`; no `-e`, no `-u` |
| `fish` | `<fish> --no-config <file>` | none (failures are visible through `$status` and `$pipestatus`) |

`<bash>` etc. are absolute paths (§4).

- **SH-15.** `sh` gets no options: common `/bin/sh` implementations (dash) reject `--noprofile`/`--norc`, and a non-interactive `sh` reads no startup file once `ENV` is cleared.
- **SH-16.** In bash, `pipefail` is set with the `-o pipefail` option, so the script text is unchanged and line numbers match the plan. A failing command in the middle of a bash or sh script doesn't stop it; the script's exit status is the leaf's.
- **SH-33.** `zsh` and `fish` are Unix-only and used only when named (`shell:` or `defaults.shell`); detection never picks them. `zsh --no-rcs` still reads `/etc/zshenv`, which zsh can't skip; `fish --no-config` reads no configuration ([ADR 0014](../adr/0014-remaining-features.md)).
- **SH-17.** **PowerShell prologue.** Blokky inserts `$ErrorActionPreference = 'Stop';` (followed by a space) at the start of the first line of the script that isn't blank, a comment, or a `using` statement. The prologue shares that line, so line numbers in error messages stay exact ([ADR 0011](../adr/0011-pwsh-prologue.md)). A `param(` block at that position is a plan error (plan scripts receive no arguments). With the prologue, a cmdlet error ends the script with exit code 1 instead of being written to stderr while the script exits 0.
- **SH-18.** `$PSNativeCommandUseErrorActionPreference` is not set: a failing native program doesn't stop a PowerShell script, matching "no `-e`" in bash.
- **SH-19.** The exact invocation, including the prologue, is determined statically, so implementations can show it before a run.
- **SH-20.** The exit code of `pwsh -File` and `powershell -File` for a script that ends without `exit` after a failing native command is *provisional — verify in spike*; the spec will state it.

### 2.3 Choosing the shell

- **SH-21.** A `script` leaf's (or script probe's) shell is, in order: its own `shell:`, `defaults.shell`, the implementation's configuration (if it has one), then detection.
- **SH-22.** **Detection** is fixed and deterministic: on Unix, `bash` if it resolves on `PATH`, else `sh` (`$SHELL` is never consulted); on Windows, `pwsh`, else `powershell`.
- **SH-23.** A reached `script` whose shell isn't supported on the current OS (§5), or can't be resolved, fails the node. Statically false `host:` branches are pruned before this check, so portable plans work.

## 3. A leaf's environment

- **SH-24.** A leaf's environment is built as in [variables.md §7](variables.md#7-environment): the environment the run started with, the scoped `env`/`export` mappings and the `BLOKKY_*` variables; then `BASH_ENV` and `ENV` are removed, so no shell reads a startup file through them.

## 4. Executable resolution

- **SH-25.** Resolution uses **Blokky's own** `PATH`, never a node's `env`, and never the current directory or Blokky's own directory.
- **SH-26.** An argv[0] that contains a path separator (`./tools/gen`, `C:\tools\gen.exe`) is a path, resolved against the node's cwd if relative; it is not looked up on `PATH`.
- **SH-27.** On Windows, a name without an extension is tried with `.com` and `.exe` only, in that order; the `PATHEXT` variable is ignored. `.bat` and `.cmd` are never run directly (SH-10).
- **SH-28.** Shell binaries resolve the same way, unless the implementation is configured with an absolute path for that shell (for blokky-cli: the user-only key `shells.<name>.path`). On Windows, `bash` and `sh` resolve **only** through such configuration (Git Bash or MSYS), never through `PATH`, which could find `C:\Windows\System32\bash.exe`, the WSL launcher ([ADR 0003](../adr/0003-execution-defaults.md)).
- **SH-29.** The launcher receives the resolved absolute path, so platform search orders don't apply (*provisional — verify in spike*). The resolved path is part of the run result.

## 5. Shell × OS matrix

| Shell | Linux | macOS | Windows |
|---|---|---|---|
| `bash` | ✓ | ✓ | only via `shells.bash.path` (Git Bash, MSYS) |
| `sh` | ✓ | ✓ | only via `shells.sh.path` |
| `pwsh` | ✓ | ✓ | ✓ |
| `powershell` | — | — | ✓ |
| `zsh` | ✓ | ✓ | — |
| `fish` | ✓ | ✓ | — |
| `cmd` | not supported | | |

`cmd` is not supported on any OS: cmd.exe expands `%X%` textually before parsing every command, so passing values through the environment would degrade to text substitution.

## 6. Injection properties

These describe how values that reach a shell through the environment can still change what runs. They are documented hygiene; implementations may flag the common mistakes. None of them is a control ([reference.md §9](reference.md#9-security-considerations)).

- **POSIX shells.** An unquoted `$X` is split into words and globbed, so a value can inject extra arguments or file names. Write `"$X"`.
- **PowerShell variables.** An exported plan variable is an environment variable: write `$env:X`, not `$X` or `${X}` (which refer to PowerShell variables and are empty).
- **PowerShell argument passing.** PowerShell 7.3 and later pass arguments to native programs as given (`$PSNativeCommandArgumentPassing`); Windows PowerShell 5.1 re-quotes them and mishandles empty strings and embedded double quotes. Prefer `exec` for native programs with variable arguments.
- **`.cmd` shims from PowerShell.** `npm`, `npx`, `pnpm`, `yarn` and other `.cmd`/`.bat` files re-parse their arguments in cmd.exe, so a variable argument is exposed to `%X%` expansion and cmd metacharacters. The safe alternative is an `exec` leaf that runs the package's JavaScript entry point with `node` ([ADR 0006](../adr/0006-shims-and-license.md)).
- **Argument injection.** A value starting with `-` is read as an option by most programs. Put `--` before item values, captures and inputs passed as arguments, where the program supports it.
- **Dynamic code.** Running a variable as code (`eval`, `source`, `.`, `sh -c "$X"`, `iex`, `Invoke-Expression`, a variable in command position) is dynamic code; implementations may flag it for review (§7).

## 7. Script analysis

- **SH-30.** The language doesn't require analysing `script` text. Implementations that flag dynamic code or common mistakes for review MAY analyse it heuristically; what they detect is implementation-defined (for blokky-cli: [`leaves`](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/contracts/leaves-and-validation.md) and its lint rules). A missed case is a review aid failing, not a security failure: `script` text is always shown in full.
- **SH-32.** Execution never switches between `exec` and `script` automatically.
