# Examples

Blokky plans that show every language feature. All of them use the canonical form and validate against [`schema/blokky.schema.json`](../schema/blokky.schema.json).

- **[`basics/`](basics/):** one short plan per feature or pair of features to compare.
- **[`scenarios/`](scenarios/):** seven longer plans for real tasks, each combining many features.

Each file starts with a comment that says what it does, what it needs and whether it changes anything, followed by a `# Run:` line with the command to run it. No implementation is released yet, so these commands describe how a plan is meant to be run.

For the rules behind each feature, see the [reference](../spec/reference.md). The [conformance suite](../conformance/) tests the same features more strictly.

## Basics

### Structure and flow

| Example | Shows |
|---|---|
| [do-sequence](basics/do-sequence.blokky.yaml) | `do`: children one after another |
| [all-parallel](basics/all-parallel.blokky.yaml) | `all` with `concurrency` and `fail_fast` |
| [any-fallback](basics/any-fallback.blokky.yaml) | `any`: the first child that succeeds |
| [race-watchdog](basics/race-watchdog.blokky.yaml) | `race`: the first child to finish decides |
| [if-else](basics/if-else.blokky.yaml) | `if` / `then` / `else` |
| [when-guard](basics/when-guard.blokky.yaml) | `when`: skip a node |
| [host-branches](basics/host-branches.blokky.yaml) | `host:` conditions, decided before the run |
| [finally-cleanup](basics/finally-cleanup.blokky.yaml) | `finally`: cleanup that always runs |
| [cwd-nesting](basics/cwd-nesting.blokky.yaml) | `cwd` inherited and resolved through nesting |
| [tempdir](basics/tempdir.blokky.yaml) | a temp dir owned by the run, removed when the node succeeds |
| [return-early](basics/return-early.blokky.yaml) | `return`: end a sequence early |
| [return-in-loop](basics/return-in-loop.blokky.yaml) | `return` in a loop body (next iteration) and in an `if` branch |

### Leaves and shells

| Example | Shows |
|---|---|
| [exec-vs-script](basics/exec-vs-script.blokky.yaml) | `exec` (argv) compared with `script` (shell text) |
| [choose-shell](basics/choose-shell.blokky.yaml) | `shell:` for a script |
| [env-export-secrets](basics/env-export-secrets.blokky.yaml) | `env`, `export` and secret values |
| [ignore-errors-ok-exit](basics/ignore-errors-ok-exit.blokky.yaml) | `ignore_errors` compared with `ok_exit` |
| [container-build](basics/container-build.blokky.yaml) | running a leaf in a container, with `env_pass` |
| [keep-descendants-detach](basics/keep-descendants-detach.blokky.yaml) | `keep_descendants: detach`: start a daemon |

### Variables and outputs

| Example | Shows |
|---|---|
| [inputs-constraints](basics/inputs-constraints.blokky.yaml) | plan `inputs` with defaults and constraints |
| [vars-constants](basics/vars-constants.blokky.yaml) | plan-level `vars` as constants |
| [set-templates](basics/set-templates.blokky.yaml) | `set` with templates |
| [set-in-branches](basics/set-in-branches.blokky.yaml) | `set` in both branches of an `if` |
| [capture-text](basics/capture-text.blokky.yaml) | `capture`: stdout into a variable |
| [capture-json-fields](basics/capture-json-fields.blokky.yaml) | `capture` of JSON fields |
| [capture-file](basics/capture-file.blokky.yaml) | `capture_file` for large or binary output |
| [outputs](basics/outputs.blokky.yaml) | returning `outputs` from a plan |

### Conditions and checks

| Example | Shows |
|---|---|
| [conditions-tour](basics/conditions-tour.blokky.yaml) | condition subjects, operators and `all`/`any`/`not` |
| [probe-conditions](basics/probe-conditions.blokky.yaml) | probes: a command decides the condition |
| [command-check](basics/command-check.blokky.yaml) | `command:`: is a tool installed? |
| [assert-check](basics/assert-check.blokky.yaml) | `assert` with `message` and `code` |
| [fail-with-code](basics/fail-with-code.blokky.yaml) | `fail` with a code |
| [log-levels](basics/log-levels.blokky.yaml) | `log` and its levels |
| [sleep-conditional](basics/sleep-conditional.blokky.yaml) | `sleep` guarded by `when` |

### Loops

| Example | Shows |
|---|---|
| [for-count](basics/for-count.blokky.yaml) | `for` over a count |
| [for-each](basics/for-each.blokky.yaml) | `for` over a list |
| [for-items-fields](basics/for-items-fields.blokky.yaml) | `for` over JSON `items` with `fields` |
| [for-lines](basics/for-lines.blokky.yaml) | `for` over `lines`, with and without `keep_blank` |
| [for-glob](basics/for-glob.blokky.yaml) | `for` over a `glob`, with `max_items` |
| [for-matrix](basics/for-matrix.blokky.yaml) | `for` over a `matrix` |
| [for-collect](basics/for-collect.blokky.yaml) | `collect`: gather a capture from every iteration |
| [while-batches](basics/while-batches.blokky.yaml) | `while`: work in batches while any work is left |
| [while-carry](basics/while-carry.blokky.yaml) | `while` with `carry`, `index` and `collect`: walk history to the last tag |
| [until-polling](basics/until-polling.blokky.yaml) | `until`: poll until a condition holds |
| [until-json-poll](basics/until-json-poll.blokky.yaml) | `until` on a JSON field; a non-JSON response means "not done yet" |
| [until-pagination](basics/until-pagination.blokky.yaml) | Pagination with a cursor: `carry` passes `next` to the next page, `collect` gathers the pages, `index` numbers them |

### Retries, time and concurrency

| Example | Shows |
|---|---|
| [retry-backoff](basics/retry-backoff.blokky.yaml) | `retry` with backoff and a numbered attempt |
| [retry-on-code](basics/retry-on-code.blokky.yaml) | `retry` only for some errors |
| [timeout-vs-attempt-timeout](basics/timeout-vs-attempt-timeout.blokky.yaml) | `timeout` compared with `attempt_timeout` |
| [lock-one-at-a-time](basics/lock-one-at-a-time.blokky.yaml) | `lock`: one run at a time |
| [services-in-order](basics/services-in-order.blokky.yaml) | background `services`, started in order, with readiness |

## Scenarios

| Scenario | Task | Features it combines |
|---|---|---|
| [changed-files-lint](scenarios/changed-files-lint.blokky.yaml) | Lint the files changed on a branch with the right linter per type | `return`, `command:` conditions, `if`, `for` `lines`/`items`, `all`, `collect`, `set`, `ok_exit`, `ignore_errors` |
| [cross-platform-setup](scenarios/cross-platform-setup.blokky.yaml) | Set up a Node.js clone on Linux, macOS and Windows | `host:` conditions, `when`, `race`, `any`, `retry`, `sleep`, `fail`, scripts in bash/zsh/pwsh |
| [deploy-health-check](scenarios/deploy-health-check.blokky.yaml) | Deploy a systemd service, check health, roll back on failure | `sudo -n` leaves, `lock`, `until`, `if`, `set`, `fail` |
| [dotnet-build-test](scenarios/dotnet-build-test.blokky.yaml) | Build and test a .NET solution with a per-project summary | `lock`, `for` `glob`, `all`, `collect`, `capture_file`, `finally`, `retry` |
| [integration-tests](scenarios/integration-tests.blokky.yaml) | Integration tests against containers and the API | `services`, `container` with mounts, `lock`, secrets, `finally` |
| [release-matrix](scenarios/release-matrix.blokky.yaml) | Cross-compile a Go tool and publish a GitHub release | `for` `matrix`, `tempdir`, secrets from the environment, `finally`, `retry` |
| [wait-for-ci](scenarios/wait-for-ci.blokky.yaml) | Wait for a GitHub Actions run and check its result | `until` polling with `on_body_failure: stop`, `for` `items`, `capture` of JSON, `assert`, `outputs` |
