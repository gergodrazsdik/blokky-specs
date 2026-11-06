# 0015: Setting variables: `set` and `vars`

- Status: accepted
- Date: 2026-11-06
- Questions: none from the brief; a gap raised by the maintainer after `1.0.0-draft.1`

## Context and problem statement

Variables could only come from inputs, captures (running a command), loop variables and `tempdir` paths. Choosing a value in an `if`/`else`, or naming a constant used in several places, needed `exec: [echo, …]` plus `capture`, or an input the caller could override. The maintainer asked for a way to set variables, including plan-level constants.

The existing model constrained the design: variables are single-assignment (shadowing is an error), a capture inside an `if` branch is "possibly undefined" afterwards, and executed values never concatenate strings (`${X}` only in display strings). The questions were asked as multiple choices with examples, on 2026-11-06; the value question was re-asked after a discussion of why string concatenation had been excluded.

## Considered options

| Question | Options (chosen in bold) |
|---|---|
| Shape | **a `set` node kind**; a `let` node kind; a `vars:` modifier on any node |
| Values | **literals, whole-value references and `${}` templates (in `set` and `vars` only)**; literals and references only |
| Assigning more than once | **once per path (single assignment; definite assignment through branches)**; mutable |
| Plan-level constants | **a root `vars:` mapping**; a `set` node at the start; fixed inputs |

## Decision outcome

All answers follow the recommendation; the value question's recommendation changed during the discussion (below).

### `set`

`set: { NAME: value, … }` is a node kind that binds variables and starts no process. Its bindings are scoped like captures: visible to later siblings, their descendants, and after the enclosing `do`.

### Values and templates

A value is a literal, a whole-value reference (`{ var: X }`, `{ from_env: NAME }`, each optionally `secret: true`), or a **template**: a string with `${X}` placeholders, as in display strings (`$${` escapes). Templates are allowed only in `set` and `vars` values; every executed argument stays a literal or one whole variable.

- An undefined variable in a template fails the node (`BK_UNDEFINED_VARIABLE`).
- A value built from any secret part is secret.
- There are no functions (case, replace, substring) and there won't be: templates only join strings.

**Why templates after all:** "no concatenation" was chosen for reviewability and to keep the language small, not for security: values never pass through a shell parser (an `exec` element is one argument; `script` sees variables only as environment variables), so a template can't inject shell syntax, and what it can do (add `../` to a path, `?x=` to a URL) is what the same bash line can do. Without templates, building `v1.2.3-linux` needs a `script` with `echo` and `capture`: a shell and a process, which is less reviewable. Confining templates to `set`/`vars` keeps one visible place where strings are built; the static view shows the template.

### Single assignment, once per path

- Setting a name that is already bound is an error, as for every binding.
- A name bound in **every** branch of an `if` (both `then` and `else`), or by **every** child of an `any` or `race`, is definitely bound after the node succeeds; bound in only some, it is "possibly undefined" (a warning when used without `defined`). The same rule applies to captures.
- Two sequential siblings binding the same name is an error (this was implied by the shadowing rule; it is now explicit).

### `vars`

A root-only key `vars: { NAME: value, … }`, bound in the plan scope after the inputs and before anything runs, in order. Values follow the `set` rules but may only use inputs, earlier `vars` and `from_env`; never a value produced by running something. Root modifiers (`name`, `cwd`, `when`, `env`) may use them. The caller can't override them.

### Modifiers on `set`, `log`, `fail` and `sleep`

Asked while reviewing this change: `timeout`, `finally` and `ignore_errors` were valid on every kind, but on `set`, `log` and `fail` they mean nothing. These nodes start no process and take no time, so a timer never fires; there is nothing to clean up after them; and ignoring a `fail` is a no-op, while ignoring a failed `set` silently leaves variables unbound. The maintainer decided to remove them: on `set`, `log` and `fail` only `name` and `when` are valid (plus `for` on `log`); the others are plan errors. A follow-up question applied the same to `sleep`: a `timeout` on it is just a shorter `sleep`, it can only end early by cancellation (which `ignore_errors` never hides), and there is nothing to clean up after a wait, so `sleep` also takes only `name` and `when`.

### Consequences

- Good: values chosen in branches and named constants need no process and no shell.
- Good: tags, URLs and file names can be built without `script`.
- Neutral: definite assignment through branches is a small static analysis that implementations must perform.
- Bad: the language now has a string-building construct; "no functions" must be held firmly in the review.
- Neutral: "universal modifiers" are no longer universal; the validity matrix lists the exceptions.

## More information

- Applied in: `spec/reference.md` (§2.12, §6, §7, §8), `spec/variables.md` (VA-56 to VA-61), `spec/syntax.md` (§4, §7), `spec/glossary.md`, `spec/results.md`, `schema/blokky.schema.json`, `ROADMAP.md`.
- Tracker: T-0055.
