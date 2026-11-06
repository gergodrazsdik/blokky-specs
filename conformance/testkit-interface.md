# Testkit interface

Status: **draft** (`1.0.0-draft`, not yet finalized)

This document is normative for the **testkit**: the fake program that conformance cases run instead of real tools ([README.md](README.md), CF-4). It defines the command-line interface and the observable behaviour on Unix (Linux, macOS) and Windows. It is implementation-independent: any implementation of the language can build its own testkit from it (for blokky-cli: `blokky-testkit`, a .NET AOT app that is never shipped in release archives; [ADR 0006](../adr/0006-shims-and-license.md)). Normative keywords are used as defined in [syntax.md §1](../spec/syntax.md#1-conventions). Rules carry IDs (`TK-n`).

## 1. General

- **TK-1.** The testkit is **one executable**, `blokky-testkit` (`blokky-testkit.exe` on Windows), invoked as `blokky-testkit <command> [arguments] [options]`. Options start with `--`, take their value as the next argument, and may appear in any order after the command unless a command says otherwise; `--` ends the options. It needs no runtime, configuration or network.
- **TK-2.** **Durations** use the plan grammar ([syntax.md §6.5](../spec/syntax.md#65-durations)), plus `0s`. Before use, every duration is multiplied by `TESTKIT_TIME_SCALE` (a decimal greater than 0 and at most 1, default 1), so cases keep their timing relations in the scaled clock mode (CF-39). **Sizes** use the plan's size grammar ([syntax.md §6.6](../spec/syntax.md#66-sizes)) or a bare number of bytes.
- **TK-3.** **Text** arguments are taken as given (UTF-8 on Unix; UTF-16 on Windows, written as UTF-8). **Hex** arguments are pairs of hex digits (`ff00`), so cases can produce any bytes.
- **TK-4.** **Output** goes only where a command says. Every write is flushed at once, so the order of writes is the order the reader sees on a merged pipe (EM-19). The testkit writes nothing else to stdout. On a usage error it writes one line starting with `blokky-testkit:` to stderr.
- **TK-5.** **Invocation log.** If `TESTKIT_LOG` is set to a path, every invocation first appends one line of compact JSON to that file, then acts:

  ```json
  {"name":"blokky-testkit","argv":["sleep","1m","--ignore-term"],"pid":4242,"ppid":4240,"cwd":"/tmp/case-17"}
  ```

  `name` is the invoked name without `.exe` (an alias name, TK-6); `argv` is the arguments after the program name, after alias expansion. Appends from concurrent processes MUST NOT interleave within a line (an exclusive lock on the file, or one write of the whole line in append mode). A failure to write the log exits with 124 before acting.
- **TK-6.** **Aliases.** Invoked under a name other than `blokky-testkit` (its basename without `.exe`), the testkit reads `<name>.testkit-args` from its own directory: UTF-8, one argument per line, LF-separated, no trailing empty argument. Those arguments are inserted before its own arguments. A missing or unreadable file exits with 125. Runners create aliases by copying, hard-linking or symlinking the executable (CF-21); a symlink is resolved for the directory but not for the name.
- **TK-7.** **Common options**, accepted by every command except `argv` (TK-12), before any `--`:
  - `--pid-file FILE`: write the process's pid and a newline to `FILE` before acting.
  - `--cwd-check DIR`: exit with 125 unless the working directory is `DIR` (compared after resolving symlinks; case-insensitively on Windows).
- **TK-8.** **Signals.** Unless a command says otherwise, the testkit keeps the default dispositions: SIGTERM, SIGINT and SIGHUP end it (Unix), and so do CTRL_BREAK and CTRL_C when it has a console (Windows). It never reads stdin unless the command says so, and never touches the terminal except in `info` (TK-17).

### 1.1 Exit codes

| Code | Meaning |
|---|---|
| 0 | Success, unless the command defines another result. |
| 1–122 | Command-defined, or set with `--exit`. |
| 123 | The command or option isn't supported on this platform (for example `die` on Windows). |
| 124 | An internal failure: a state, log or output file couldn't be read or written. |
| 125 | A usage error: unknown command or option, missing or malformed value, a failed `--cwd-check`. |
| other | Only when a case asks for it with `exit` or `--exit`. |

Cases MUST NOT expect 123–125 as a command's result; a runner MAY report a leaf exit of 124 or 125 as a broken case.

## 2. Commands

| Command | Purpose | Section |
|---|---|---|
| `exit` | Exit with a code. | TK-9 |
| `print` | Write text or bytes to stdout and stderr, with delays; then exit or hang. | TK-10 |
| `cat` | Copy stdin to stdout. | TK-11 |
| `argv` | Print the received arguments. | TK-12 |
| `env`, `getenv` | Print environment variables. | TK-13 |
| `sleep` | Sleep; optionally ignore and record graceful stop requests. | TK-14 |
| `spawn` | Start descendants that outlive the testkit or hold its output open. | TK-15 |
| `alive` | Check whether recorded processes are still alive. | TK-16 |
| `info` | Report pid, user, cwd, platform and terminal. | TK-17 |
| `write-file`, `read-file` | Write and read files. | TK-18 |
| `count`, `flaky` | Count invocations in a state file; fail N times, then succeed. | TK-19 |
| `listen` | Listen on a loopback TCP port after a delay. | TK-20 |
| `die` | Terminate by a signal. | TK-21 |

### 2.1 `exit`

- **TK-9.** `exit CODE` exits with `CODE`, a decimal integer: 0–255 on Unix, 0–4294967295 on Windows (an unsigned 32-bit value). Anything else is a usage error.

  ```yaml
  exec: [blokky-testkit, exit, '3']
  ```

### 2.2 `print`

- **TK-10.** `print OP... [--newline lf|crlf|none] [--exit CODE | --hang]` performs the operations in order, then exits with `CODE` (default 0), or with `--hang` sleeps until it is stopped. Operations:

| Operation | Effect |
|---|---|
| `--out TEXT`, `--err TEXT` | Write `TEXT` and the line ending to stdout or stderr. |
| `--out-hex HEX`, `--err-hex HEX` | Write the bytes exactly, without a line ending (invalid UTF-8, NUL, a BOM, a lone CR). |
| `--out-fill SIZE`, `--err-fill SIZE` | Write `SIZE` bytes of 63 `x` characters and an LF, repeated; the last line is cut at `SIZE`. |
| `--sleep DURATION` | Pause before the next operation. |
| `--close-out`, `--close-err` | Close the stream; later writes to it are errors (exit 124). |

`--newline` sets the line ending of `--out`/`--err` for the whole invocation: `lf` (default), `crlf` or `none`. With no operations, `print` writes nothing.

```yaml
# a ready line after a delay, then keep running (services `ready: { output }`)
- exec: [blokky-testkit, print, --sleep, 2s, --out, 'Now listening', --hang]
# interleaved streams with stderr: merge (EM-19)
- exec: [blokky-testkit, print, --out, a, --err, b, --out, c]
# a NUL byte in stdout (BK_CAPTURE_NUL)
- exec: [blokky-testkit, print, --out-hex, '610062']
# 2 MiB of stdout (BK_CAPTURE_TOO_LARGE)
- exec: [blokky-testkit, print, --out-fill, 2MiB]
# a service that becomes ready, then crashes (EM-64)
- exec: [blokky-testkit, print, --out, ready, --sleep, 3s, --exit, '7']
```

### 2.3 `cat`

- **TK-11.** `cat [--to stdout|stderr]` copies stdin byte for byte to stdout (default) or stderr until end of input, then exits with 0. With empty stdin (EM-17) it writes nothing and exits at once; it never waits for a terminal.

### 2.4 `argv`

- **TK-12.** `argv [ARG...]` writes the arguments it received after `argv`, as a compact JSON array of strings and an LF, to stdout: `["a b","-x",""]`. `--` and options are not interpreted; every argument is printed. On Windows, `argv --raw` instead writes the raw command line (`GetCommandLineW`) as one JSON string, so cases can check the quoting of SH-9; on Unix `--raw` exits with 123. In an alias, the alias arguments (TK-6) come first.

### 2.5 `env` and `getenv`

- **TK-13.** `env NAME...` writes a compact JSON object of the named variables to stdout, in argument order, `null` for an unset variable, then an LF: `{"CI":"true","BASH_ENV":null}`. `env --all` writes every variable, sorted by name (ordinal). `getenv NAME` writes the value and an LF, and exits with 3 if `NAME` is unset. Names are looked up as the OS does (case-insensitively on Windows).

  ```yaml
  exec: [blokky-testkit, env, BLOKKY_RUN_ID, BASH_ENV, ENV]   # VA-44, EM-16
  capture: { RUN_ID: .BLOKKY_RUN_ID }
  ```

### 2.6 `sleep`

- **TK-14.** `sleep DURATION [--ignore-term] [--ignore-term-for DURATION] [--record-signals FILE] [--exit CODE]` sleeps, then exits with `CODE` (default 0).
  - `--ignore-term`: the graceful stop request (EM-26) is ignored for the whole sleep: SIGTERM, SIGINT and SIGHUP on Unix; CTRL_BREAK and CTRL_C on Windows. Only the forced kill ends the process.
  - `--ignore-term-for D`: requests in the first `D` after start are ignored; a request after that ends the process as by default.
  - `--record-signals FILE`: each received request appends its name and an LF to `FILE` (`SIGTERM`, `SIGINT`, `SIGHUP`, `CTRL_BREAK`, `CTRL_C`), before it is acted on or ignored. A forced kill can't be recorded.

### 2.7 `spawn`

- **TK-15.** `spawn [--depth N] [--count N] [--release-output] [--escape MODE] [--pids FILE] [--wait] -- COMMAND...` starts descendants, each running `blokky-testkit COMMAND...`:
  - `--count N` (default 1) direct children; with `--depth N` (default 1) each child is itself a `spawn` of the same shape, one level less deep, so the tree has `count^1 + … + count^depth` descendants, and the leaves of the tree run `COMMAND`.
  - By default descendants inherit stdin, stdout and stderr, so they hold the leaf's output open after the testkit exits (EM-20). `--release-output` gives them the null device for all three.
  - `--escape MODE` makes the direct children try to leave the process tree: `setsid` (Unix: a new session and process group), `double-fork` (Unix: a daemon reparented away from the testkit), `breakaway` (Windows: `CREATE_BREAKAWAY_FROM_JOB`, which fails if the job forbids it). A mode unsupported on the platform exits with 123. These test EM-22's best-effort cleanup.
  - `--pids FILE` appends the pid of every descendant, one per line, as each starts.
  - Without `--wait`, the testkit exits with 0 as soon as its direct children have started. With `--wait`, it waits for them and exits with the first non-zero exit code among them, or 0.

  ```yaml
  # a leaf whose child keeps stdout open for 30s after the leaf exits
  exec: [blokky-testkit, spawn, --pids, pids.txt, --, print, --sleep, 30s, --out, late]
  ```

### 2.8 `alive`

- **TK-16.** `alive FILE` reads pids, one per line, and writes a compact JSON array of those still alive, then an LF; it exits with 0 if none is alive and 1 otherwise. A pid that now belongs to another program counts as alive; cases keep the window short. Cases use it in a later node or `finally` to check that descendants were stopped (EM-21, EM-22), and runners MAY use it after the run.

### 2.9 `info`

- **TK-17.** `info` writes one compact JSON object and an LF to stdout:

| Field | Value |
|---|---|
| `pid`, `ppid` | Its own and its parent's process id. |
| `user` | The effective user name. |
| `uid`, `euid` | The real and effective user ids (Unix); `null` on Windows. |
| `elevated` | Windows: whether the token is elevated; Unix: whether `euid` is 0. |
| `cwd` | The working directory, as the OS reports it. |
| `os`, `arch` | As the `host:` subject names them (`linux`, `macos`, `windows`; `x64`, `arm64`). |
| `tty` | Unix: whether opening `/dev/tty` succeeds, that is whether it has a controlling terminal (EM-15). Windows: whether it is attached to a console. |
| `stdin` | `null-device`, `pipe`, `file` or `terminal`: what its stdin is (EM-17). |

### 2.10 `write-file` and `read-file`

- **TK-18.** `write-file PATH (--text TEXT | --hex HEX) [--append] [--newline lf|crlf|none]` creates or overwrites `PATH` (relative to the cwd), or appends to it, and creates no parent directories. `--text` adds the line ending (default `lf`); `--hex` writes the bytes exactly. `read-file PATH` copies the file's bytes to stdout and exits with 3 if it doesn't exist.

### 2.11 `count` and `flaky`

- **TK-19.** Both keep a counter in a state file: a decimal integer, 0 if the file doesn't exist. Each invocation increments it under an exclusive lock, so concurrent invocations each get a distinct number, and writes the new value and an LF to stdout.
  - `count --state FILE` exits with 0.
  - `flaky --state FILE --fail-times N [--code C]` exits with `C` (default 1) while the new value is at most `N`, then with 0: "fail N times, then succeed".

  ```yaml
  - name: fails twice, then succeeds
    retry: true
    max: 3
    every: 0s
    exec: [blokky-testkit, flaky, --state, attempts.txt, --fail-times, '2']
  ```

### 2.12 `listen`

- **TK-20.** `listen --port P [--after DURATION] [--out TEXT] [--exit-after DURATION] [--exit CODE]` waits `--after` (default `0s`), then listens on `127.0.0.1:P` and, where available, `[::1]:P`. Once listening it writes `--out` (if given) and an LF to stdout. It accepts connections and closes each at once without reading or writing. It runs until it is stopped, or with `--exit-after D` exits with `--exit` (default 0) `D` after it started listening. If the port can't be bound it writes a line to stderr and exits with 4.

  ```yaml
  services:
    - name: api
      exec: [blokky-testkit, listen, --port, '47010', --after, 1s]
      ready: { port: 47010, open: true }
  exec: [blokky-testkit, exit, '0']
  ```

### 2.13 `die`

- **TK-21.** `die --signal NAME` (Unix) resets the disposition of signal `NAME` (`SIGTERM`, `SIGKILL`, `SIGSEGV`, `SIGABRT`, …) to the default and sends it to itself, so the parent sees a termination by that signal (`BK_SIGNAL`, EM-23). On Windows it exits with 123.

## 3. Platform summary

| Behaviour | Unix | Windows |
|---|---|---|
| Graceful stop request ignored by `sleep --ignore-term` | SIGTERM, SIGINT, SIGHUP | CTRL_BREAK, CTRL_C (with a console) |
| `spawn --escape` | `setsid`, `double-fork` | `breakaway` |
| `argv --raw` | 123 | the raw command line |
| `die` | the named signal | 123 |
| Exit code range | 0–255 | 0–4294967295 |
| `info.tty` | controlling terminal | console attached |
| Alias executable | any name, with `<name>.testkit-args` | `<name>.exe`, with `<name>.testkit-args` |

An implementation of the testkit is conformant when every command and option above behaves as specified on the platforms it targets; it MAY add commands and options, which cases don't use.
