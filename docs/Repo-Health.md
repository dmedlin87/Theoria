# Repository Health Report

## OpenSSF Scorecard Summary

- **Target Score:** ≥ 8.0 (first automated report will publish via the `security-scorecard.yml` workflow).
- **Current Posture:** Historical runs unavailable; expect initial score in the 6–7 range due to missing dependency updates, unsigned releases, and absent provenance metadata.
- **Immediate Remediations:**
  1. Land the hardened CI/CD stack (CodeQL, Scorecard, SBOM, dependency policies) – implemented in this change set.
  2. Enforce conventional commits and branch protection so Scorecard detects review and test requirements.
  3. Enable signed container/image builds with provenance attestation before first production release.

## Key Risks and Prioritized Fixes

| Priority | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| P0 | Missing automated SAST/SBOM/reporting pipelines | Unknown exposure to critical vulnerabilities | Activate CodeQL, Scorecard, and CycloneDX workflows; surface SARIF in security tab. |
| P0 | Lack of threat model & disclosure policy | Delayed incident response, poor triage | Publish `SECURITY.md` and `THREATMODEL.md`; route reports via security@ alias. |
| P1 | Direct access from framework layers into persistence/utilities | Tight coupling blocks modular refactors | Execute modularization roadmap in `docs/Modularity-Plan.md` and enforce via architecture tests. |
| P1 | Dependency drift across Python & Node ecosystems | Increased CVE surface, breakage risk | Dependabot schedule with grouped updates; add policy for emergency patch windows. |
| P2 | Secrets passed via environment without rotation guidance | Risk of long-lived credentials | Document rotation cadence & use of vault/SM; add tests covering encryption paths. |

## Hardening Actions

- **Pinned Dependencies:** All GitHub Actions pinned to commit SHA; CycloneDX outputs lock dependencies for review.
- **Permissions:** Workflows default to `contents: read` and granular scopes per job; hardened against token leakage.
- **Untrusted Code Execution:** PR-triggered jobs avoid persistent credentials, run with minimal permissions, and guard caches with explicit keys.
- **Cache Safety:** Disabled implicit cache reuse; all caches keyed on lockfiles to prevent poisoned artefacts.
- **Artifact Integrity:** SBOMs uploaded as immutable build artifacts; roadmap includes in-toto attestations for staged builds (see `DEPLOYMENT.md`).

## Dependency Risk & Update Plan

### Python
- Core runtime published via extras in `pyproject.toml` (install with `pip install .[api] -c constraints/guardrails.txt -c constraints/prod.txt` plus `[ml]`/`[dev]` as needed).
- **Grouped Releases:**
  - **Monthly functional upgrades:** Framework stack (FastAPI, SQLAlchemy, Celery).
  - **Bi-weekly security sweeps:** Cryptography, JWT, HTTP clients.
  - **Quarterly ML stack:** numpy/scipy/scikit-learn/FlagEmbedding after compatibility matrix review.
- **Breaking-Change Windows:** Align ORM & FastAPI upgrades with dedicated staging branches and smoke tests.

### Node / Web
- Lockfile ensures deterministic installs.
- Dependabot groups `next`/`react`/`typescript` and linting packages separately to control rollout velocity.
- Introduce Playwright smoke tests before promoting Next.js major versions.

### Supply-Chain Controls
- SBOM generation (Python + Node) on each CI run.
- Dependabot configuration for both ecosystems with weekly cadence and security-only immediate patches.
- Plan to adopt Sigstore provenance for container builds as part of the SLSA roadmap (see `DEPLOYMENT.md`).

## Observability & Testing Coverage

- Global coverage gate set to **80% project-wide** and **90% for `theo/services/api/app/core`** (see pytest configuration).
- Architecture guardrails fail CI on cross-module imports.
- CodeQL + Pyre typed checks flagged as future enhancements for deeper dataflow coverage.

## Outstanding TODOs

1. Implement domain/application adapter reshuffle per modularity plan (Phase 2).
2. Add container signing + provenance attestation once deployment pipeline is containerized.
3. ✅ OWASP ZAP baseline scan now targets the staging API via the `STAGING_API_BASE_URL` secret, uploads SARIF, and gates merges on High alerts.
4. Evaluate secrets scanning tooling (Trufflehog or GitHub Advanced Security) post-onboarding.
