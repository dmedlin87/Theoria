# ADR 0002: Harden CI/CD with Security Gates

- Status: Accepted
- Date: 2024-05-01

## Context

Previous CI ran linting and tests but lacked SAST, SBOMs, and supply-chain protections. To meet OWASP ASVS L1+ and SLSA targets, we must extend pipelines with security tooling while minimizing risk from untrusted contributions.

## Decision

- Create dedicated workflows for CodeQL and OpenSSF Scorecard, both pinned to commit SHAs.
- Generate CycloneDX SBOMs for Python and Node artifacts on every CI run and publish as build artifacts.
- Restrict `GITHUB_TOKEN` scopes to least privilege and avoid privileged runs on forked PRs.
- Configure Dependabot to manage dependency drift with grouped updates.

## Consequences

- Slightly longer CI times due to additional scans.
- Increased visibility into security posture; failing checks block merges until resolved.
- Automated dependency alerts reduce manual triage and accelerate patching.
