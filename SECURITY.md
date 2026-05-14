# Security Policy

## Supported versions

Ragbot ships from `main`. Only the current `main` branch is supported. The
project does not maintain back-ports to prior tags.

| Version | Supported |
| --- | --- |
| `main` (v3.4+) | Yes |
| Tagged releases prior to v3.4 | No |

If you are running an older tagged release, upgrade to the latest `main`
before reporting a vulnerability. Patches are not back-ported.

## Reporting a vulnerability

Report security issues through
[GitHub Security Advisories](https://github.com/synthesisengineering/ragbot/security/advisories/new).
This is the only channel that allows coordinated disclosure with a private
discussion thread.

Please include:

- A description of the vulnerability, including the impacted code path.
- Steps to reproduce, ideally as a minimal repro repository or a small diff
  against `main`.
- Your assessment of the severity (CVSS or qualitative).
- Whether you have a suggested fix.

You will receive an acknowledgement within five business days. Triage and
fix work happen in a private branch; we open the public PR and credit the
reporter once the patched release is ready, unless you request anonymity.

## Triage cadence

Two layers of triage run continuously.

**Automated (weekly).** Dependabot scans `requirements.txt` (Python) and
`web/package.json` (npm) on a weekly schedule. New PRs land for any
security advisory with a fix path. The full configuration is at
[`.github/dependabot.yml`](./.github/dependabot.yml).

**Manual (per Phase-5 of each minor release).** Before every minor release,
a manual triage pass categorises every open Dependabot alert as
`real-exposure`, `transitive-only`, `false-positive`, or `accepted-risk`,
and either pins, overrides, or documents an ignore. The most recent triage
log is the public source of truth for every decision:

- [2026-05 triage (Phase 5 of v3.4)](./docs/security/dependabot-triage-2026-05.md)

Future triage logs follow the same naming convention
(`docs/security/dependabot-triage-YYYY-MM.md`) and are linked above as
they land.

## Confidentiality boundary

This repository is public. Security issues that involve data flowing
through a private deployment of Ragbot belong in that deployment's
incident-response channel, not on this repo. Please report only issues
that reproduce against a vanilla checkout of `main`.
