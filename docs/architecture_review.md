# Theoria Architecture Review (2025-02)

## A) Executive Summary
- The platform enforces authentication and secret preconditions at startup, but it still relies on a global `THEO_ALLOW_INSECURE_STARTUP` flag that can silently bypass both controls, leaving production safety dependent on manual discipline rather than guardrails.【F:theo/services/api/app/main.py†L135-L305】【F:theo/application/facades/runtime.py†L5-L16】
- Core ingestion stages are modular and instrumented, yet the default error policy never retries transient failures, so the pipeline fails fast on flaky sources despite having circuit-breaker utilities elsewhere in the codebase.【F:theo/services/api/app/ingest/orchestrator.py†L24-L108】【F:theo/services/api/app/ingest/stages/base.py†L39-L129】【F:theo/services/api/app/resilience.py†L1-L110】
- Retrieval and reranking share a coherent abstraction, but reranker crashes are swallowed without telemetry, masking degraded relevance when expensive models fail or drift.【F:theo/services/api/app/services/retrieval_service.py†L151-L205】
- Data modelling captures rich theological metadata, though heavy JSON fields and missing partial indexes complicate reporting and threaten query performance as the corpus scales.【F:theo/services/api/app/db/models.py†L49-L220】
- Guardrails against SSRF and unsafe ingestion are thorough (scheme, host, CIDR checks), helping align with security goals for handling arbitrary user documents.【F:theo/services/api/app/ingest/network.py†L26-L199】
- Observability spans, structured logs, and Prometheus metrics are well integrated but only activate when optional dependencies are installed, leaving production operability contingent on deployment discipline.【F:theo/services/api/app/telemetry.py†L200-L307】
- Docker Compose codifies a full-stack topology (Postgres, Redis, API, MCP, Web) yet exposes default credentials and volumes without guidance on production hardening or cost controls.【F:infra/docker-compose.yml†L1-L88】
- Frontend API proxies centralize auth header management and trace propagation, but environment defaults leak localhost URLs, suggesting gaps in deployment configuration management.【F:theo/services/web/app/api/search/route.ts†L1-L55】【F:theo/services/web/app/lib/api.ts†L1-L59】
- Secrets persistence uses Fernet encryption but only if `SETTINGS_SECRET_KEY` is present; the lack of automated rotation or secret-source integration complicates compliance stories.【F:theo/application/facades/settings.py†L15-L488】【F:theo/application/facades/settings_store.py†L1-L104】
- Documentation (README, BLUEPRINT, telemetry guide) is rich, and an ADR register now captures foundational choices (architecture, CI, typing), yet gaps remain for operational guardrails (e.g., when to enable `allow_insecure_startup`).【F:README.md†L1-L126】【F:docs/BLUEPRINT.md†L1-L120】【F:docs/telemetry.md†L1-L120】【F:docs/adr/0001-hexagonal-architecture.md†L1-L19】【F:docs/adr/0002-ci-security-guardrails.md†L1-L16】【F:docs/adr/0003-testing-and-coverage.md†L1-L16】

## B) Quality Attribute Scorecard (0 = Poor, 3 = Excellent)
| Attribute | Score | Rationale |
| --- | --- | --- |
| Security | 2 | Strong request authentication and SSRF guardrails, but reliance on `THEO_ALLOW_INSECURE_STARTUP` and static credentials leaves misconfiguration risk.【F:theo/services/api/app/main.py†L135-L305】【F:theo/services/api/app/ingest/network.py†L26-L199】 |
| Reliability | 1 | No retries in ingestion policy and silent reranker failures undermine resilience despite available circuit-breaker utilities.【F:theo/services/api/app/ingest/stages/base.py†L39-L129】【F:theo/services/api/app/services/retrieval_service.py†L151-L205】 |
| Performance | 2 | Hybrid search architecture and optional reranking are efficient, but JSON-heavy schema and lack of query governance may degrade at scale.【F:theo/services/api/app/db/models.py†L49-L220】【F:theo/services/api/app/services/retrieval_service.py†L151-L205】 |
| Cost | 1 | Compose stack provisions multiple services without autoscaling/capacity guidance; reranker retries may thrash expensive models when misconfigured.【F:infra/docker-compose.yml†L1-L88】【F:theo/services/api/app/services/retrieval_service.py†L151-L205】 |
| Sustainability | 1 | No energy/capacity sizing guidance; optional reranker and caching degrade to noop instead of adaptive throttling, risking wasted compute.【F:theo/services/api/app/services/retrieval_service.py†L151-L205】【F:theo/services/api/app/ai/router.py†L1-L200】 |
| Operability | 2 | Telemetry hooks and `/metrics` endpoint are present, yet dependent on optional installs and lacking deployment automation for tracing exporters.【F:theo/services/api/app/telemetry.py†L200-L307】 |
| Modularity | 2 | Clear service boundaries and dependency injection, but ingestion error policy tightly couples stage reliability to a single global default.【F:theo/services/api/app/ingest/orchestrator.py†L24-L108】【F:theo/services/api/app/ingest/stages/base.py†L39-L129】 |
| Data Architecture | 2 | Schema models the domain but mixes relational and JSON blobs without lifecycle/index strategy, complicating analytics and migrations.【F:theo/services/api/app/db/models.py†L49-L360】 |
| Observability | 2 | Structured logs, metrics, and trace propagation exist, yet require manual toggles (`THEO_ENABLE_CONSOLE_TRACES`) and optional deps, risking uneven coverage.【F:theo/services/api/app/telemetry.py†L200-L307】【F:docs/telemetry.md†L1-L120】 |

## C) Findings
| Severity | Area | Finding | Evidence | Why it matters | Recommendation | Effort | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| High | Security | `THEO_ALLOW_INSECURE_STARTUP` bypasses both auth and secret enforcement without environment scoping, so a mis-set flag in production disables all access controls and secret encryption.|【F:theo/services/api/app/main.py†L135-L305】【F:theo/application/facades/runtime.py†L5-L16】【F:theo/services/api/app/ai/rag/cache.py†L47-L144】|Single env var can nullify primary defenses (auth, secret storage, Redis requirement), increasing breach likelihood.|Restrict the flag to explicit development profiles: fail fast unless `ENVIRONMENT=dev` and document hard production overrides. Consider replacing with signed config or build-time feature flags.|Medium|Platform Security|
| High | Reliability | Default ingestion policy never retries transient stage failures, so network hiccups or parser flakiness abort the entire pipeline despite existing resilience primitives.|【F:theo/services/api/app/ingest/stages/base.py†L39-L129】【F:theo/services/api/app/ingest/orchestrator.py†L24-L108】【F:theo/services/api/app/resilience.py†L1-L110】|Causes ingestion outages for recoverable errors, degrading data freshness and user trust.|Adopt a resilient error policy (e.g., `ResiliencePolicy`) with per-stage retry/backoff and circuit breakers, configurable via settings.|High|Ingestion Team|
| Medium | Reliability/Observability | Reranker exceptions are swallowed silently, so degraded search quality or cost overruns go unnoticed.|【F:theo/services/api/app/services/retrieval_service.py†L151-L205】|Users get lower relevance without alerts, undermining perceived quality while still incurring model costs.|Log exceptions with workflow telemetry, expose counters for reranker failures, and surface health in `/metrics`.|Low|Search Platform|
| Medium | Data | Document/passages tables store polymorphic JSON without governance (no partial indexes, TTL, or migration notes), risking slow queries and migration pain.|【F:theo/services/api/app/db/models.py†L49-L360】|Unbounded JSON fields hurt planner selectivity and complicate analytics/reporting as corpus grows.|Define JSON schema fragments, add GIN/partial indexes for frequent keys, and document migration/versioning strategy.|Medium|Data Engineering|
| Medium | Security/Config | Docker Compose ships with default Postgres credentials and no guidance for secrets/volume hardening, encouraging insecure defaults in staging/prod.|【F:infra/docker-compose.yml†L1-L88】|Developers may promote insecure compose configs to shared environments, exposing data and enabling lateral movement.|Document secure overrides (env var templates), enforce secrets via `.env.example`, and add lint/checks preventing default creds outside dev.|Low|DevOps|
| Medium | Operability | Telemetry relies on optional dependencies and manual env toggles, so production deployments can quietly run without traces/metrics.|【F:theo/services/api/app/telemetry.py†L200-L307】【F:docs/telemetry.md†L1-L120】|Missing observability impairs incident response and SLO monitoring.|Add startup checks that fail or warn loudly when telemetry backends are absent in non-dev environments; supply IaC snippets for exporters.|Medium|SRE|

## D) Hotspots
1. `theo/services/api/app/main.py` – centralizes startup policy, auth, and router wiring; refactoring here can enforce environment-aware security gates and telemetry requirements.【F:theo/services/api/app/main.py†L135-L305】
2. `theo/services/api/app/ingest/orchestrator.py` & `stages/base.py` – ingestion flow control; introducing resilient policies and per-stage configuration yields high reliability ROI.【F:theo/services/api/app/ingest/orchestrator.py†L24-L108】【F:theo/services/api/app/ingest/stages/base.py†L39-L129】
3. `theo/services/api/app/resilience.py` – reusable circuit breaker implementation currently unused by ingestion; integrating it reduces failure cascades.【F:theo/services/api/app/resilience.py†L1-L110】
4. `theo/services/api/app/services/retrieval_service.py` – reranker orchestration; better error handling and metrics improve search quality and cost transparency.【F:theo/services/api/app/services/retrieval_service.py†L151-L205】
5. `theo/services/api/app/db/models.py` – schema definitions; targeted indexing and JSON governance improve performance and analytics flexibility.【F:theo/services/api/app/db/models.py†L49-L360】
6. `infra/docker-compose.yml` – stack definition; production hardening and secrets management can be codified here for team-wide consistency.【F:infra/docker-compose.yml†L1-L88】
7. `theo/application/facades/settings_store.py` – secret persistence; expanding rotation and secret source integration improves compliance posture.【F:theo/application/facades/settings_store.py†L1-L104】
8. `theo/services/api/app/telemetry.py` – instrumentation core; enforce required exporters and unify observability bootstrap.【F:theo/services/api/app/telemetry.py†L200-L307】
9. `theo/services/web/app/api/search/route.ts` – proxy and auth management; central spot to introduce feature flags, rate limiting, and config validation.【F:theo/services/web/app/api/search/route.ts†L1-L55】
10. `theo/services/api/app/ai/router.py` – LLM routing logic; rich area to embed cost ceilings, sustainability policies, and model-level governance.【F:theo/services/api/app/ai/router.py†L1-L200】

## E) Action Plan
- **Now (0–4 weeks)**
  - Gate `THEO_ALLOW_INSECURE_STARTUP` behind explicit development environments and add CI checks preventing accidental enablement.【F:theo/services/api/app/main.py†L135-L305】
  - Implement logging/metrics for reranker failures and add smoke tests to ensure regressions surface quickly.【F:theo/services/api/app/services/retrieval_service.py†L151-L205】
  - Update Docker Compose and `.env` docs with secure defaults and warnings against using sample creds beyond local dev.【F:infra/docker-compose.yml†L1-L88】

- **Next (1–2 quarters)**
  - Introduce configurable retry/backoff policies for ingestion stages, leveraging existing resilience utilities; document per-source SLAs.【F:theo/services/api/app/ingest/stages/base.py†L39-L129】【F:theo/services/api/app/resilience.py†L1-L110】
  - Define JSON field governance (schemas, indexes, retention) and codify migrations for the passages/documents tables.【F:theo/services/api/app/db/models.py†L49-L360】
  - Automate telemetry bootstrap by bundling required dependencies and enforcing exporter configuration in staging/prod pipelines.【F:theo/services/api/app/telemetry.py†L200-L307】

- **Later (Roadmap)**
  - Integrate secrets storage with managed services (e.g., AWS KMS, HashiCorp Vault) and plan rotation workflows to meet compliance audits.【F:theo/application/facades/settings_store.py†L1-L104】
  - Expand cost-awareness in the LLM router (dynamic budgets, sustainability signals) and expose metrics for carbon/cost per workflow.【F:theo/services/api/app/ai/router.py†L1-L200】
  - Extend ADR coverage to include security modes (e.g., `allow_insecure_startup`), ingestion resilience, and observability strategy to aid future audits.【F:docs/BLUEPRINT.md†L1-L120】【F:docs/adr/0001-hexagonal-architecture.md†L1-L19】

## F) Appendices
- **Service Topology**: Docker Compose defines Postgres, Redis, API, MCP, and Web containers with shared storage volumes and port mappings.【F:infra/docker-compose.yml†L1-L88】
- **Configuration Sources**: Settings facade loads environment variables with defaults for database, Redis, embedding models, auth, and ingestion guardrails.【F:theo/application/facades/settings.py†L15-L488】
- **Observability Signals**: `telemetry.py` emits Prometheus counters/histograms and optional OpenTelemetry spans; `/metrics` endpoint exposed when Prometheus available.【F:theo/services/api/app/telemetry.py†L200-L307】【F:theo/services/api/app/main.py†L240-L305】
- **Security Controls**: `security.py` enforces API key/JWT validation and attaches principals to requests; ingestion network hardens against SSRF with scheme/host/IP checks.【F:theo/services/api/app/security.py†L1-L179】【F:theo/services/api/app/ingest/network.py†L26-L199】
- **Decision Log**: ADRs document architectural layering, CI security guardrails, and testing standards; new entries are still needed for runtime safety toggles and resilience defaults.【F:docs/adr/0001-hexagonal-architecture.md†L1-L19】【F:docs/adr/0002-ci-security-guardrails.md†L1-L16】【F:docs/adr/0003-testing-and-coverage.md†L1-L22】
