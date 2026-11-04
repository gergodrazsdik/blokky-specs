# Security policy

## Reporting a vulnerability

Please report vulnerabilities through **GitHub private vulnerability reporting**: on the repository's **Security** tab, choose **Report a vulnerability** ([direct link](https://github.com/gergodrazsdik/blokky-specs/security/advisories/new)). Do not open a public issue.

In this repo, a vulnerability is usually a **language-level** problem: a construct that hides what will run from review, lets a plan do more than the equivalent shell, or makes masking or validation contracts misleading. Implementation bugs belong in [blokky-cli](https://github.com/gergodrazsdik/blokky-cli/security/advisories/new); if unsure, report in either.

## Supported versions

None yet. The specification is a pre-1.0 draft with no released versions.

## Response

Blokky has a single maintainer, so responses are best effort. I aim to acknowledge a report within a week.

## Scope

How Blokky reasons about security is described in the blokky-cli threat model ([docs/security/threat-model.md](https://github.com/gergodrazsdik/blokky-cli/blob/main/docs/security/threat-model.md); the design brief's §1.2 summarizes it):

- **Blokky is not a sandbox.** The baseline is "the same thing without Blokky": what an agent could do with a plain shell call.
- **In scope:** anything that makes using Blokky *less* safe than the equivalent shell, or that hides what will run.
- **Hygiene vs controls:** strict-mode lint, secret masking and display sanitization are hygiene, not security boundaries. The agent runner's permission system, the hook and the validator are the controls.
