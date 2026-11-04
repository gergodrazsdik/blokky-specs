# 0004: Validator protocol and input scope (open-question batch 4, language part)

- Status: accepted
- Date: 2026-11-04
- Questions: Q9, Q-in1, Q-in3, Q-in4, Q-in5

## Context and problem statement

The [specification-phase brief](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/design/brief.md) §4 lists questions that must be answered before the language spec draft is written. Batch 4 covers validation, configuration and inputs. Its language-level part is recorded here: the validator protocol (a contract specified in this repo, `spec/leaves-and-validation.md` and `schema/validator.schema.json`) and the scope of plan inputs. The hook, approval binding, configuration and lint answers from the same batch are in [blokky-cli ADR 0003](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/adr/0003-validation-config-lint.md).

Each question was asked as a multiple choice with a recommendation, on 2026-11-04. The options considered are listed per decision below; the chosen one is marked.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| Q9a transport | **spawn per request, JSON on stdin and stdout**; long-lived JSON-lines process; local socket or HTTP daemon |
| Q9b verdicts and failures | **allow/deny/ask, any failure → ask**; any failure → deny; allow/deny only |
| Q9c timeout | **10s**; 5s; 30s |
| Q-in1 nested-plan node | **not planned**; `later` node kind with a reserved `call` keyword |
| Q-in3, Q-in4, Q-in5 | **later, if needed; on the ROADMAP, no keywords reserved**; `--input-file` in v0.1 |

## Decision outcome

All answers follow the recommendation.

### Q9: validator protocol

**Transport.** The validator is an executable configured only at user level (blokky-cli ADR 0003). For each request, Blokky:

1. starts it with no arguments, in the invocation cwd, with Blokky's own environment and no terminal;
2. writes one request JSON document to its stdin and closes stdin;
3. reads one response JSON document from its stdout (size-capped), and keeps a bounded tail of its stderr for diagnostics.

The exit code is ignored; only the response counts. The process tree is killed when the timeout fires. One process handles one request, so validators are stateless and can be written in any language.

**Request** (`validator.schema.json`, own `schema_version`): the `leaves` document for the invocation (units, flags, plan-dependent effects, plan SHA-256, spec version, `inputs`, `inputs_complete`, `inputs_sha256`), plus the invocation context: the command (`hook check` or `validate`), the cwd, the runner name when called from the hook, and the allow-listed flags of the `blokky run` command line.

**Response:**

```json
{
  "schema_version": "1",
  "decision": "allow",
  "reason": "all units match the team policy",
  "units": [ { "id": "/do/1", "decision": "allow", "reason": "known CI poll" } ]
}
```

- `decision` is `allow`, `deny` or `ask`; `reason` is required for `deny` and `ask`.
- `units` is optional. It gives per-unit verdicts, and it is the only way to allow a unit that forces `ask` by default (dynamic code, `exec_env_risk` and the other constructs in blokky-cli ADR 0003, Q-g).
- **Combination:** the result is `deny` if `decision` or any unit verdict is `deny`. It is `allow` only if `decision` is `allow` and every unit that forces `ask` has an explicit unit `allow`. Otherwise it is `ask`.
- Unknown fields are ignored; an unknown `decision` value is a failure.

**Failures become `ask`.** A timeout, a crash, a missing or non-executable path, malformed or oversized JSON, or a response that doesn't match the schema yields `ask`, with the failure as the reason. Nothing is silently allowed, and a broken validator doesn't lock the agent out; a human decides. `blokky validate` exits 0 for allow, 5 for ask and 6 for deny (blokky-cli ADR 0002).

**Timeout:** 10s by default (a user-only config key).

### Q-in1: native nested plans

Not planned. A `call`/`plan:` node with `inputs:` and child `outputs` would be a module system, against "small". Nested runs stay an `exec` of `blokky run`, analysed as nested plans in `leaves` (brief §3.9, A8). No keyword is reserved.

### Q-in3, Q-in4, Q-in5: later, if needed

`--input-file` (with `--expect-inputs-sha256`, never auto-allowed), env-sourced secret inputs, and references in today's literal fields (`timeout: { var: T }`) are candidates, revisited after v0.1 usage. They are listed on the [ROADMAP](../ROADMAP.md) as candidates; no keyword or field shape is reserved for them. Q-in5 would be additive: accepting a reference where a literal is required today breaks no plan.

### Consequences

- Good: validators are trivial to write (read JSON, print JSON), and the `leaves` document is the single description of what runs, for humans, rules mode and validators alike.
- Good: a validator failure can never turn into an allow.
- Neutral: process start-up is paid on every hook call; a slow validator should cache on its own.
- Neutral: the per-unit verdict list is what lets a validator allow dynamic constructs explicitly, so validators that only return a top-level `allow` get `ask` for those plans.
- Bad: input-related conveniences (input files, env-sourced inputs, parameterized literals) wait until usage shows they are needed.

## More information

- Brief: §3.3 (inputs), §3.9 (leaves, validator, hook), §4 (questions).
- Tracker: T-0011; the answers are linked from the [open-questions table](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/plan/TRACKER.md#open-questions).
- Spec files that apply these answers: `spec/leaves-and-validation.md`, `schema/validator.schema.json`, `schema/leaves.schema.json` (Q9); `spec/reference.md` (Q-in1 and the literal fields, Q-in5).
- Companion: [blokky-cli ADR 0003](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/adr/0003-validation-config-lint.md) (Q10, Q11, Q-a, Q-b, Q-c, Q-d, Q-g, Q-in2, Q-in6).
