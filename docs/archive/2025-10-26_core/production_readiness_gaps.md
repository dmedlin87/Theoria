> **Archived on 2025-10-26**

# Production Readiness Gaps

This document captures the highest-risk items currently blocking a production-ready release of Theoria. Each issue lists the impact, supporting evidence, and recommended next steps.

## 1. Inflight ledger restart handling fails concurrency test
- **Impact:** High – Deduplication ledger loses completed generations after a router restart. Waiters can block indefinitely and the shared output is never replayed, breaking request fan-out and causing user-visible timeouts.
- **Evidence:** `pytest` suite fails on `test_wait_for_inflight_preserves_completed_output_after_restart_failure`, demonstrating that the preserved output is not observed once a restarted router recreates the inflight row.【8c5ff9†L1-L88】 The defect stems from `SharedLedger.wait_for_inflight`, which does not surface the preserved success payload when a `waiting` row is recreated after success.【F:theo/services/api/app/ai/ledger.py†L520-L870】
- **Remediation:** Fix `wait_for_inflight` so that any new `waiting` row that still carries a completed output immediately replays the preserved record to all waiting threads. Add regression coverage using the failing test to verify the fix.

## 2. Signed container releases ship without vulnerability scanning
- **Impact:** High – Production images are built, signed, and published without a CVE scan, so critical vulnerabilities can ship undetected despite having provenance metadata.
- **Evidence:** The CI/CD audit notes container vulnerability scanning as a medium-severity gap with a recommendation to add Trivy before signing.【F:audit/cicd_pipeline_review.md†L412-L439】 The `Release Containers` workflow currently builds, signs, and attests the image but contains no Trivy/Grype step to gate releases.【F:.github/workflows/deployment-sign.yml†L18-L160】
- **Remediation:** Add a blocking vulnerability scan (e.g., `aquasecurity/trivy-action`) before signing/attestation and upload the SARIF results. Fail the workflow on any High/Critical findings.

## 3. Security contact GPG key is missing
- **Impact:** Medium – Coordinated disclosure cannot be encrypted as promised in the security policy, eroding trust with external reporters.
- **Evidence:** `SECURITY.md` references a pending `docs/keys/security.asc` artifact for the `security@Theoria.com` address, but the key directory is absent from the repository.【F:SECURITY.md†L12-L28】【c9db24†L1-L3】
- **Remediation:** Publish the referenced ASCII-armored GPG key (or update the policy with an alternate secure channel) and ensure the disclosure process is verifiable.

## Next Steps
Prioritize the ledger concurrency fix and container scanning addition before cutting a production branch. Once these blockers are resolved, publish the security contact key and rerun the full test suite (`pytest`) to confirm all gates are green.
