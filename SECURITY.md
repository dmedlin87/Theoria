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
- **DAST:** Planned OWASP ZAP baseline run on staging (tracked in `Repo-Health.md`).
- **Secrets Management:** Long-lived credentials stored in managed secret store (Vault/Azure Key Vault) – never committed.
- **Incident Response:** Centralized contact via security mailing list; create follow-up advisory in `docs/advisories/` when needed.
