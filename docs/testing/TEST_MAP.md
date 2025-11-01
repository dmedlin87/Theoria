# Theoria Test Map

## Inventory Overview

### Backend Python Services (`theo/services/api/app`)
- **Core settings & infrastructure**: `core.settings`, `core.settings_store`, `core.database`, `core.secret_migration`, `tracing`, `telemetry`.
- **Database access**: SQLAlchemy models in `db.models`, utility types in `db.types`, migration runner `db.run_sql_migrations`, seed utilities `db.seeds`, feedback persistence `db.feedback`.
- **Ingestion pipeline**: Parsers & normalizers in `ingest.parsers`, `ingest.osis`, `ingest.metadata`, chunking logic `ingest.chunking`, pipeline orchestration `ingest.pipeline`, persistence `ingest.persistence`, sanitization and network fetchers.
- **AI / retrieval**: Retrieval orchestration in `retriever.hybrid`, `retriever.verses`, `retriever.documents`, annotation helpers `retriever.annotations`, export utilities. RAG logic under `ai.rag`, `ai.passage`, `ai.trails`, `ai.digest_service`, `ai.watchlists_service`, server registry `ai.registry`, clients `ai.clients`.
- **Analytics & reporting**: Telemetry writers `analytics.telemetry`, topic digests `analytics.topics`, watchlist analytics, OpenAlex integrations.
- **Domain models**: Pydantic models in `models.*` covering analytics, AI, documents, jobs, search, transcripts, trails, verses.
- **Research modules**: Report builders and domain logic under `research.*` (notes, morphology, variants, commentaries, contradictions, historicity, geo integrations).
- **Routes / API surface**: FastAPI routers in `routes.*` for ingest, search, documents, analytics, research, transcripts, trails, export, features, jobs.
- **Creators & enrichment**: `creators.service`, `creators.verse_perspectives`, metadata enrichment `enrich.metadata`.
- **Workers**: Celery app & tasks in `workers.tasks` orchestrating ingestion, enrichment, summarisation, watchlist scheduling, index refresh.
- **Ranking**: Feature engineering `ranking.features`, metrics `ranking.metrics`, re-ranker orchestrator `ranking.re_ranker`.

### CLI Utilities (`theo/services/cli`)
- Ingestion helpers, redaction scripts, pgvector maintenance (`refresh_hnsw.py`).

### Geo Services (`theo/services/geo`)
- Geo dataset loaders and GIS helpers (used by research modules).

### Frontend (`theo/services/web`)
- **Next.js App Router** with routes: `app/search`, `app/research`, `app/chat`, `app/upload`, verse detail `app/verse/[osis]`, document view `app/doc/[id]`, admin dashboards `app/admin/*`, copilot area `app/copilot/*`.
- **Route handlers**: API route handlers under `app/api/(search|analytics|ingest)`.
- **Shared components**: `app/components` and `app/copilot/components`.
- **App context**: Providers in `app/context` (feature flags, user session, analytics).
- **Utilities**: Query helpers in `app/lib`, typed client in `app/lib/generated/api.ts`.

### Search Infrastructure
- Hybrid pgvector search in `retriever.hybrid` with ANN/HNSW and lexical blend.
- Ranking heuristics in `ranking.features` and `metrics`.
- CLI + Celery integration for refreshing vector indexes and evaluating recall.

### Celery Tasks (`workers.tasks`)
- `validate_citations`, `process_file`, `process_url`, `enrich_document`, `generate_document_summary`, `send_topic_digest_notification`, `generate_topic_digest`, `refresh_hnsw`, `run_watchlist_alert`, `build_deliverable`, `schedule_watchlist_alerts`, `refresh_creator_verse_rollups` plus helpers for cached chat sessions and citation normalisation.

The contributor workflow for starting Postgres fixtures, running targeted suites, and interpreting coverage reports now lives in [`CONTRIBUTING.md`](../../CONTRIBUTING.md#postgres--pgvector-testcontainer-fixture). Cross-check those sections when spinning up a new suite locally.

## Planned Test Suites

| Suite | Scope | Key Fixtures / Infra | Coverage Goals | Notes & Deferrals |
| --- | --- | --- | --- | --- |
| `pytest` unit (core models & utils) | Pydantic models, ingestion sanitizers, metadata normalisation, analytics helpers, ranking metrics | Pure unit fixtures, Hypothesis strategies for OSIS references, faker for metadata | ≥95% statements / ≥90% branches in covered modules | Defer slow integrations (OpenAlex HTTP) – will mock client boundary |
| `pytest` integration (DB) | SQLAlchemy models, repositories, ingestion persistence, hybrid retrieval against pgvector | Transactional Postgres via Testcontainers; alembic migrations applied once per session | Same as unit | Full-text search weight tuning out of scope for initial pass |
| `pytest` workers | Celery task behaviour (retries, idempotency, serialization) using celery.contrib.pytest | In-memory broker backend for fast unit runs; optional live worker marker for CI nightly | ≥90% statements tasks module | Live worker test to assert beat schedule wiring deferred pending CI resource allocation |
| `pgvector smoke` | kNN vs ANN parity for deterministic embeddings, distance operator correctness | Postgres+pgvector container seeded with fixtures, coverage aggregated with backend | Included in backend thresholds | Performance benchmark to remain as non-gating metric due to CI time |
| `Hypothesis` property suites | OSIS parsing/normalisation, chunking invariants, metadata cleaning | Shared Hypothesis strategies module, seeded example DB for round-trip | Counted with pytest | Additional DSL for TEI parsing deferred |
| `Vitest` frontend unit | React components (search results, chat composer, upload flow, admin tables) | Testing Library + MSW for API mocks, jsdom | ≥90% statements global, ≥80% per-file floor | Visual regressions deferred to Playwright visual diff follow-up |
| `Playwright` server action tests | Next.js server actions, route handlers, streaming flows | Launch dev server with seeded fixtures, reuse backend Testcontainers | Tagged `@smoke` subset for PRs, `@full` nightly | Authentication SSO handshake simulated via test-only token exchange |
| `Playwright` E2E flows | Top journeys: ingest file → index → search → evidence → save/export; chat digests; admin watchlist review | Compose backend worker + Postgres containers, seed vector data, run headless | Must record traces on failure, integrate with GitHub Actions artifact upload | Additional locale/RTL coverage deferred |
| `make test:changed` | Run Vitest on changed files using `--changed` filter, fallback to full run when no git context | N/A | N/A | Implementation tied to Nx caching deferred |

### Known Gaps / Deferrals
- No automated load/perf benchmarking in CI (documented in ROADMAP).<br>- Geo services integration tests require large shapefiles; plan to stub via contract tests instead.<br>- Third-party API contract tests (OpenAlex, external sermon sources) to be covered via recorded cassettes in separate initiative.<br>- Accessibility snapshot tooling (axe) to be introduced after initial Playwright smoke coverage is stable.

### Regression Data Factories
- `tests/fixtures/regression_factory.py` synthesises documents, passages, and OSIS references using `Faker` and `pythonbible`.
- Tests can request the `regression_factory` fixture (seeded to `2025`) to build deterministic RAG prompts, guardrail payloads, and other regression datasets.
- Re-create golden/performance artefacts by instantiating `RegressionDataFactory` with the default seed; randomness is seeded so repeated runs produce identical output.

## Next Steps Checklist
- [ ] Stand up reusable Postgres + pgvector Testcontainer fixtures.
- [ ] Add Hypothesis-based property suites for OSIS parser and chunking heuristics.
- [ ] Implement Celery retry/idempotency tests with celery.contrib.pytest fixtures.
- [ ] Configure Vitest coverage thresholds and component tests for key UI surfaces.
- [ ] Script Playwright journeys with smoke/full tags and CI trace uploads.
- [ ] Wire GitHub Actions workflows with coverage gates and artifact uploads.
- [x] Document developer flows in `CONTRIBUTING.md` (DB/bootstrap, targeted runs). See [Running Tests](../../CONTRIBUTING.md#targeted-pytest-execution) for the living reference.
