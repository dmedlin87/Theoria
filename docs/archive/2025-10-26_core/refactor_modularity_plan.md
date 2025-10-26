> **Archived on 2025-10-26**

# Refactor Roadmap for Modularity and Resilience

This document consolidates the previously proposed refactor tasks with the most impactful follow-up recommendations. The focus is on maximising modularity and ensuring robust error handling throughout the Theoria codebase.

## 1. Establish an Application Composition Root
- Replace the hard-coded router tuple in `theo/app/main.py` with a discovery-driven registry so each feature self-registers its HTTP, worker, and scheduled jobs surfaces.
- Create an `AppContext` that encapsulates settings, logging, telemetry, database/session factories, and external integrations. Routers and services should obtain dependencies via this context to eliminate scattered `get_settings()` lookups and hidden singletons.
- Document the resulting dependency graph to baseline current architecture and guide future modularisation efforts.

## 2. Carve Out Domain Service Layers
- Introduce service modules (e.g., `ingestion_service.py`, `retrieval_service.py`) to mediate between FastAPI routers and underlying pipelines.
- Adopt FastAPI dependency injection so routes import service interfaces instead of implementation helpers, enabling swap-in fakes for tests.
- Provide unit coverage for services without spinning up FastAPI, using dependency overrides on the new application context.

## 3. Modularise the Ingestion Pipeline
- Break the ingestion pipeline into explicit stages (acquire → normalise metadata → parse → chunk → persist → index) defined in `theo/ingest/stages/` with clear contracts.
- Introduce an orchestrator that composes stages, returns structured results, and respects pluggable error policies (retry, quarantine, fallback).
- Move temporary-file management, metadata enrichment, and Celery/inline persistence decisions from route handlers into the orchestrator services.

## 4. Split Retrieval and Ranking Engines
- Extract lexical, vector, reranking, and annotation enrichment logic into interchangeable providers behind a `Retriever` interface.
- Allow deployments to toggle or sequence providers, with orchestrator-level caching, timeout budgets, and fallback heuristics (e.g., lexical-only mode when ANN fails).

## 5. Introduce a Unified Error Taxonomy and Resilience Toolkit
- Create `theo/app/errors.py` with domain-specific exception classes and machine-readable codes that translate into consistent HTTP responses through global FastAPI handlers.
- Wrap external I/O (network calls, filesystem, embeddings) in resilience utilities that surface structured failure metadata for orchestrators.
- Extend middleware to include error codes, trace identifiers, retry/fallback metadata, and feed telemetry for alerting.

## 6. Refine the Domain Data Layer
- Decompose the monolithic SQLAlchemy models into bounded contexts (ingest artifacts, notebooks, cases, telemetry) with dedicated repository interfaces.
- Ensure repositories return typed results/entities and centralise session management and retry logic.

## 7. Expand Observability and Guardrails
- Instrument each new module boundary for stage latency, retry counts, cache hit ratios, and fallback invocations.
- Add guardrails such as per-tenant rate limiting, payload size caps, and anomaly detection for ingestion frequency using the telemetry hooks.

## 8. Testing and Rollout Strategy
- Create contract tests for pipeline stages, fault-injection suites for adapters, and golden datasets for retrieval scoring.
- Use feature flags to gradually migrate ingestion sources and retrieval backends, monitoring telemetry before retiring legacy code paths.

## Sequencing Guidance
1. Baseline architecture and introduce the application context/registry (Sections 1 & 2).
2. Modularise ingestion with stage orchestration while adopting the new error taxonomy (Sections 3 & 5).
3. Proceed with retrieval engine decomposition and domain data layer refinement (Sections 4 & 6).
4. Enhance observability, guardrails, and testing assets in parallel with rollouts (Sections 7 & 8).

This roadmap balances structural improvements with resilience upgrades, ensuring each refactor increment delivers clearer module boundaries and more robust error handling.
