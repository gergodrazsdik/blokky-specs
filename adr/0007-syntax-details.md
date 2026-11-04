# 0007: Syntax details (draft round 1)

- Status: accepted
- Date: 2026-11-04
- Questions: none from the brief; raised while drafting `spec/syntax.md` (T-0015)

## Context and problem statement

Writing `spec/syntax.md` needed four values and rules that the brief and ADRs 0001–0006 left open. The brief fixes the shape of the rules (plan size and depth are capped; inputs have per-value and total caps; durations have no bare numbers; empty lists are rejected) but not the values. One rule also conflicted with ADR 0005, which gives `mounts: []` a meaning.

Each question was asked as a multiple choice with a recommendation, on 2026-11-04.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| Plan size and nesting depth | 1 MiB / depth 64; 256 KiB / depth 32; **4 MiB / depth 128** |
| `--input` value caps | **4 KiB per value, 32 KiB total**; 1 KiB / 8 KiB; 16 KiB / 64 KiB |
| Duration grammar | **strict integer units**; allow fractions; add a day unit |
| Empty lists vs `mounts: []` | **per-field exception**; `mounts: none`; `mount_cwd: false` |

## Decision outcome

All answers follow the recommendation except the plan caps, where the maintainer chose the looser 4 MiB / depth 128.

- **Plan caps:** at most 4 MiB of raw plan bytes and 128 levels of YAML nesting. The spec fixes both; they are not configurable, so a plan is valid or invalid everywhere.
- **Input caps:** each `--input` value at most 4 KiB, all values together at most 32 KiB, counted in UTF-8 bytes. They are a free config key; exceeding them is `BK_INPUT_TOO_LARGE`.
- **Durations:**
  - one or more `<integer><unit>` parts with units `h`, `m`, `s`, `ms`, in descending order, each at most once;
  - no leading zeros, fractions, signs or spaces;
  - positive, except in fields that allow `0s`;
  - at most 168h.
- **Empty lists** stay plan errors, except in fields whose reference entry says an empty list is meaningful. Today that is only `mounts` (*later*), where `[]` means "mount only the runtime dirs" (ADR 0005). The per-field table in `syntax.md` marks such fields.

### Consequences

- Good: `syntax.md` has no placeholders for these values.
- Neutral: 4 MiB / depth 128 leaves room for generated plans; nested-plan or agent-written plans never get near it.
- Neutral: one duration spelling per value (`1500ms`, not `1.5s`) keeps plans and the normalized plan view uniform.
- Bad: the empty-list rule now has an exception that the schema and the reference must carry.

## More information

- Applied in: `spec/syntax.md` §2.3 (caps), §5.2 (input caps), §6.5 (durations), §3.1 and §7.4 (empty lists).
- Tracker: T-0015.
