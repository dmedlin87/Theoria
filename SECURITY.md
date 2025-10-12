# Security Policy

## Supported Versions

| Version | Supported |
| --- | --- |
| `main` branch | ✅ Active | 
| Released tags ≥ `v0.5.0` | ✅ Receive security fixes |
| Older releases | ❌ Unsupported |

## Reporting a Vulnerability

- Email: `security@theoengine.com`
- GPG: `0xA1E3E2FF` (see `docs/keys/security.asc` – pending publishing)
- Response commitment: initial acknowledgement within **2 business days**, status update every **5 business days** until resolution.

Include the following:
- Affected component/module
- Proof-of-concept or reproduction steps
- Impact assessment (confidentiality/integrity/availability)
- Suggested remediation if known

## Disclosure Timeline

1. Receive and triage the report.
2. Assign severity via CVSS v3.1.
3. Develop fix in private branch with full test coverage.
4. Coordinate release window with reporter; default embargo ≤ 30 days.
5. Publish advisory with CVE (when applicable) and update changelog.

## Security Controls Mapping

| OWASP ASVS Control | Implementation | Evidence |
| --- | --- | --- |
| V2 Authentication | API key/JWT enforcement in `theo/services/api/app/security.py`; anonymous access disabled by default | `tests/api/test_security.py`, CodeQL auth checks |
| V3 Session Management | Stateless API tokens; no session identifiers stored server-side | API integration tests |
| V4 Access Control | Principal propagation & policy checks in routes/services | Pytest authorization suite |
| V5 Validation/Sanitization | Pydantic models, schema validation on inbound payloads | FastAPI validation, `pytest` request fixtures |
| V6 Stored Cryptography | Secrets encrypted-at-rest via registry migration utilities | `tests/api/test_ai_registry.py` |
| V8 Data Protection | TLS terminated at ingress (deployment guide) + hashed keys | Deployment pipeline doc |
| V10 Malicious Code | Pinned dependencies, CodeQL, Ruff static analysis | CI workflows, SARIF upload |
| V14 Configuration | Pydantic Settings / environment validation, `.env` template | `docs/authentication.md`, coverage tests |

## Additional Practices

- **Dependency Monitoring:** Dependabot weekly groups + security-only immediate updates.
- **SAST:** GitHub CodeQL (Python + JavaScript) on pull requests and default branch.
- **DAST:** Automated OWASP ZAP baseline scan of `https://staging.api.theoengine.com` each Monday (`.github/workflows/security-zap.yml`) with SARIF results surfaced in the repository security dashboard.
- **Secrets Management:** Long-lived credentials stored in managed secret store (Vault/Azure Key Vault) – never committed.
- **Secrets Scanning:** [Trufflehog](docs/security/secret-scanning.md) runs locally and in CI using the curated baseline at `docs/security/trufflehog-baseline.json`. The workflow fails if any finding falls outside that baseline and uploads the raw JSON artifact for review.
- **Incident Response:** Centralized contact via security mailing list; create follow-up advisory in `docs/advisories/` when needed.

## Secret Scanning Operations

1. **Local validation.** Engineers can reproduce CI behaviour with `python scripts/security/run_trufflehog.py` (or `trufflehog --json --regex --entropy=False --repo_path . file://.`) to generate a JSON report matching CI output. Commit the refreshed results to `docs/security/trufflehog-baseline.json` only after confirming that every entry is a sanctioned template credential.
2. **Allow-list maintenance.** The baseline file doubles as the allow-list. When a false-positive is accepted, append a new object capturing the commit hash, path, and matching string so auditors can trace the rationale. Do not delete historical entries; they evidence long-term exceptions.
3. **Escalation.** Any new detection outside the baseline must follow the remediation flow below. After remediation, update the baseline and rotate credentials to keep future scans green.

## Secrets Exposure Response

1. CI surfaces TruffleHog findings in the `trufflehog-report` artifact. Security engineering receives automatic notifications for failures on `main`.
2. Page the on-call engineer, rotate the exposed credential in its upstream system, and revoke any associated refresh tokens or API keys.
3. Purge the secret from Git history using BFG or `git filter-repo`; ensure rewritten branches are force-pushed and communicate the rewrite to collaborators.
4. File an incident ticket documenting scope, blast radius, and remediation steps; close only after rotation and history purge are verified.

## DAST Finding Triage

1. ZAP alerts appear in the GitHub Security tab once the SARIF upload from `security-zap.yml` completes.
2. Classify the alert severity (High/Medium -> 24h fix SLA, Low -> next sprint backlog) and assign ownership based on the impacted API surface.
3. Validate the issue against staging using ZAP or manual reproduction, then land fixes with regression tests. Dismiss false positives in the security dashboard with justification referencing ZAP rule IDs.
