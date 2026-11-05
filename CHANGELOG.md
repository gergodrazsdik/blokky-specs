# Changelog

All notable changes to the Blokky language specification are documented in this file. Each entry is a spec version.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the specification adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Draft glossary (`spec/glossary.md`).
- Draft syntax (`spec/syntax.md`): plan text, YAML subset, root document, inputs, scalar grammars, references and interpolation, the per-field table, pitfalls and targeted errors.
- Draft reference (`spec/reference.md`): node kinds, leaf options, modifiers, repetition, the validity matrix, rules beyond the schema and security considerations.
- Draft execution model (`spec/execution-model.md`): run lifecycle, modifier order, start order, leaf processes, time limits, cancellation, run budget and shutdown, status propagation, with rule IDs for conformance.
- Draft variables (`spec/variables.md`): namespaces, names, bindings, input values and errors, captures, scope, environment, outputs and secrets.
- Draft conditions (`spec/conditions.md`): shape, subjects, operators, composites, probes, evaluation scope and condition errors.
- Draft shells (`spec/shells.md`): `exec` splitting, Windows command lines, script files and the invocation table, shell choice, executable resolution, the shell × OS matrix, injection properties and script analysis.
- Draft containers and privilege (`spec/containers-and-privilege.md`, later milestone): the host path model, `container` (shape, lifecycle, mounts, user, nesting) and `become` (users, mechanism, files, running as root).
- Draft error catalogue (`spec/errors.md`): code rules and stability, phases and exit codes, and every built-in `BK_` code with its `detail` fields and retry behaviour.
