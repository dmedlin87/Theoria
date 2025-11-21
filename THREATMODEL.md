# Threat Model

## System Overview

Theo Engine ingests theological content, normalizes scripture references, and exposes search + AI-assisted research workflows through FastAPI, Celery workers, and a Next.js UI. Data is stored in Postgres, Redis, object storage, and optional vector databases.

## Assets

| Asset | Description | Security Goal |
| --- | --- | --- |
| Indexed corpus | User-uploaded theological documents and transcripts | Confidentiality, integrity |
| Provider credentials | API keys for OpenAI, Anthropic, Azure, webhooks | Confidentiality |
| Research outputs | Generated notes, sermons, exports | Integrity |
| Audit logs & metrics | Telemetry streams for monitoring | Integrity, availability |
| Configuration secrets | JWT keys, database URLs | Confidentiality |

## Trust Boundaries

1. **Public Internet ↔ API Gateway:** Incoming HTTPS traffic authenticated via API keys/JWTs.
2. **API ↔ Application Core:** FastAPI controllers call application facades; enforcement of principal context occurs here.
3. **Application ↔ Persistence/AI Providers:** Outbound calls to databases, embeddings, and LLMs executed via adapters.
4. **Internal Workers:** Celery/worker processes communicate via broker; only trusted network segments should access the broker.

## Threat Actors

- External attackers (anonymous)
- Authenticated users with malicious intent
- Compromised third-party API providers
- Insider operators with elevated access

## Top Abuse Cases & Mitigations

| Abuse Case | Attack Vector | Mitigation |
| --- | --- | --- |
| Credential stuffing / token theft | Replay of leaked API keys | Short-lived API keys, allow-listing, monitoring failed auth attempts |
| Prompt injection & model exfiltration | Malicious document content influences AI outputs | Domain validators sanitize inputs; deterministic retrieval layer ensures citations align with documents; future plan for prompt sandboxing |
| Stored XSS in exported content | Untrusted HTML in ingestion sources | Sanitization on ingestion, Markdown serialization, unit tests covering exporters |
| SSRF via ingestion URLs | Attacker submits internal network URL | URL allow-list/deny-list enforcement, requests executed through safe HTTP client with blocklist |
| Data poisoning | Uploads embed false references | Domain review workflows; optional human approval queue |
| Supply-chain compromise | Malicious dependency update | Dependabot with review requirements, pinned versions, CodeQL scanning |
| Queue exhaustion / DoS | Flood Celery tasks or API endpoints | Rate limiting (planned), Celery concurrency caps, metrics alerts |

## Residual Risks

- Reliance on third-party LLM providers introduces potential data retention beyond our control; mitigate via provider agreements, anonymization, and local LLM alternatives (see Priority 5 in `docs/planning/PROJECT_IMPROVEMENTS_ROADMAP.md`).
- Local deployments may disable authentication; ensure documentation warns this is dev-only and prefer auto-generated dev keys over fully disabled auth.
- DAST coverage is limited to baseline scans; deeper authenticated scanning and API fuzzing are planned enhancements.

## Mitigation Tracking

- `docs/Repo-Health.md` records outstanding action items.
- CI workflows block merges when architecture tests or security scans fail.
- ADRs capture acceptance of residual risks and future improvements.
