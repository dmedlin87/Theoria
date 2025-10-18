# Theoria Codebase Review

_Last updated: 2025-10-13_

## Repository Overview

Theoria is a polyglot monorepo that ships a FastAPI research API, a Next.js web
client, Celery-powered background workers, and a library of supporting domain
services. The backend code lives under `theo/`, while the modern React
experience resides in `theo/services/web`. Supporting documentation, runbooks,
and architectural plans are organized under `docs/`.

## Architectural Layers

- **Domain & Application** – Core business objects and orchestration live under
  `theo/domain` and `theo/application`. Application facades provide runtime
  configuration, secrets handling, and integration seams for adapters such as
  embeddings, storage providers, and LLM presets.
- **Services** – Runtime services are grouped under `theo/services`:
  - `api` exposes the FastAPI application, SQLAlchemy ORM models, ingestion
    pipelines, retriever/reranker logic, analytics, and Celery worker entry
    points.
  - `cli` contains automation for bulk ingestion and operational scripts.
  - `web` packages the Next.js front-end.
  - `geo` manages optional geographic enrichment data.
- **Adapters** – Integration code for embeddings, storage, and third-party
  services is collected in `theo/adapters`, with implementation-specific wiring
  abstracted behind the application container (`theo/platform/application.py`,
  re-exported for services via `theo/services/bootstrap.py`).

## Backend Services

- **Configuration** – `theo/application/facades/settings.py` defines a
  Pydantic-powered settings object that loads environment variables, covers
  database and Redis connections, embedding models, rerankers, authentication
  policies, and feature flags for Case Builder and topic digests. Shared LLM
  registry primitives (secret handling, bootstrap defaults) now live in
  `theo/application/ports/ai_registry.py`.
- **API Composition** – `theo/services/api/app/main.py` builds the FastAPI app,
  registers routers from feature packages (ingestion, retrieval, analytics,
  creators, transcripts, MCP integrations), enables OpenAPI docs, and wires
  middleware for security, telemetry, and error handling.
- **Data Model** – `theo/services/api/app/db/models.py` houses SQLAlchemy models
  for documents, passages, annotations, chat sessions, case builder entities,
  ingestion jobs, and analytics tables. Vector columns leverage pgvector or
  SQLite fallbacks via custom `VectorType` definitions in
  `theo/services/api/app/db/types.py`.
- **Ingestion Pipeline** – `theo/services/api/app/ingest/pipeline.py` orchestrates
  source ingestion: normalizes content, chunks passages, generates embeddings,
  persists metadata, and emits Celery tasks for background enrichment. Web
  fetches honour configurable timeouts, size limits, and redirect caps from the
  settings facade.
- **Hybrid Retrieval & Ranking** – `theo/services/api/app/retriever/hybrid.py`
  blends vector similarity with lexical scoring, annotation boosts, and OSIS
  reference alignment. Optional reranking is provided via
  `theo/services/api/app/ranking/re_ranker.py`, which loads a local or external
  reranker model when enabled in settings. Verse-specific retrieval helpers live
  in `theo/services/api/app/retriever/verses.py` and integrate with the OSIS
  normalisation utilities in `theo/services/api/app/ingest/osis.py`.
- **Generative Workflows** – `theo/services/api/app/ai/rag.py` and the
  `creators` package implement sermon prep, transcript synthesis, and
  verse-perspective outputs that keep citations anchored to passages. Guardrails
  enforce citation drift detection and compliance with anchored references.
- **Background Jobs** – `theo/services/api/app/workers/tasks.py` configures a
  Celery app backed by Redis, schedules nightly HNSW refresh and citation audit
  jobs, validates cached chat citations, emits topic digests, and runs watchlist
  analytics. Workers resolve dependencies via the shared application container
  and operate against the same SQLAlchemy engine.
- **Telemetry & Security** – `theo/services/api/app/telemetry.py` publishes key
  workflow events (citation drift, ingest diagnostics) while `security.py`
  enforces API key and JWT auth strategies. OpenTelemetry tracing is threaded
  through retriever and ingestion paths for observability.

## Front-End Platform

- **Framework** – `theo/services/web` is a Next.js 15 (React 19) application.
  Scripts in `package.json` provide linting, Jest/Vitest unit tests, Playwright
  E2E suites, Percy visual baselines, Lighthouse smoke checks, and accessibility
  audits. Radix UI primitives, cmdk (command palette), and lucide icons power
  the UI.
- **Quality Gates** – The `scripts/quality` utilities enforce animation, a11y,
  and performance baselines documented in `docs/ui-quality-gates.md`. Playwright
  tags cover smoke, visual, and accessibility runs for CI pipelines.
- **Integration** – Environment variables `NEXT_PUBLIC_API_BASE_URL` and
  `THEO_SEARCH_API_KEY` (see `README.md`) connect the web proxy to the FastAPI
  backend, forwarding credentials as either `Authorization` or `X-API-Key`
  headers.

## Tooling & Developer Experience

- **Launcher** – `START_HERE.md` documents the PowerShell launcher that checks
  prerequisites, provisions `.env`, starts API and web services, manages health
  checks, and falls back to Docker Compose when native runtimes are missing.
- **Docker** – `docker-compose.yml` ships a dev stack with hot reload, exposing
  the API on port 8000 and the web app on port 3000 while wiring environment
  defaults for anonymous API access.
- **CLI Utilities** – `theo/services/cli` exposes ingestion helpers such as
  `ingest_folder`, alignment tools, and search experiments. Commands respect the
  same settings facade and share the ingestion pipeline with the API.
- **Scripts & Infra** – `scripts/` includes telemetry, database seeding, and
  launcher helpers. `infra/` contains TLS assets, deployment manifests, and
  observability templates referenced in `DEPLOYMENT.md` and `SECURITY.md`.

## Testing & Quality Assurance

- **Python Tests** – `pytest` is configured via `pyproject.toml` with markers
  for slow tests, red team suites, and migration-enabled runs. Architecture
  tests enforce layering boundaries under `tests/architecture`.
- **Static Analysis** – Ruff and mypy guard the backend (`pyproject.toml`),
  while type stubs live under `typings/`. The repo pins formatting with Black
  and isort configurations.
- **Front-End Tests** – The Next.js app runs ESLint, TypeScript, Jest, Vitest,
  and Playwright via npm scripts. Percy snapshots and Lighthouse smoke tests
  enforce visual and performance regressions.
- **Data Contracts** – JSON Schema specs in `docs/case_builder.schema.json` and
  contract tests under `tests/contracts` ensure API compatibility with case
  builder clients and MCP integrations.

## Data & Storage

- **Database** – SQLAlchemy models back a Postgres (or SQLite) store with tables
  for documents, passages, OSIS verse graphs, ingestion jobs, analytics events,
  and chat sessions. Migrations live in `theo/services/api/app/db/migrations` and
  can be executed via `run_sql_migrations.py`.
- **Vector Search** – `VectorType` columns map to pgvector in Postgres and
  fallback to JSON blobs for SQLite. Hybrid search loads embeddings from
  `theo/services/api/app/ingest/embeddings.py`, caching vectors based on the
  configured embedding model and dimension settings.
- **Storage** – Persisted artifacts (normalized snapshots, transcripts, exports)
  are written under `storage_root`, with optional public URLs when configured.
- **Telemetry Store** – Redis acts as both Celery broker and result backend.

## Documentation Index & Currency

The following primary docs remain authoritative and reference the implementation
above:

| Document | Purpose |
| --- | --- |
| `README.md` | Highlights, feature matrix, quick start, and service bootstrapping. |
| `START_HERE.md` | Smart launcher workflow and troubleshooting. |
| `docs/BLUEPRINT.md` | End-to-end architecture design with diagrams. |
| `docs/Repo-Health.md` | Security, dependency, and observability posture. |
| `docs/ROADMAP.md` | Strategic priorities and phased delivery. |
| `docs/UI_NAVIGATION_LOADING_IMPROVEMENTS.md` | Summary of UI polish and accessibility upgrades. |
| `SECURITY.md` & `THREATMODEL.md` | Incident response, disclosure, and threat modeling guidance. |
| `docs/testing/` | Pytest, Playwright, and quality gate runbooks. |
| `docs/runbooks/` | Incident and operations playbooks for ingestion, search, and worker recovery. |

All documents linked above have been cross-referenced against the current code
layout and configuration to ensure instructions, paths, and feature descriptions
match the latest implementation.

## Recommended Next Steps

1. Keep dependency update automation (Dependabot/ Renovate) aligned with the
   cadence outlined in `docs/Repo-Health.md` to maintain supply-chain hygiene.
2. Expand typed coverage beyond the API package by incrementally enabling mypy
   for domain and adapter modules.
3. Finish wiring reranker checkpoints via settings once the preferred model is
   finalised, ensuring the Celery tasks refresh cached scores after deployment.
4. Continue evolving `docs/testing/` with examples from new Playwright suites so
   contributors can reproduce CI checks locally.
