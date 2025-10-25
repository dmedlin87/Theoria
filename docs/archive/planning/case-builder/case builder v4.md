# Case Builder v4 Implementation Plan

> Schema reference: See [`docs/features/case-builder/case-builder.schema.json`](docs/features/case-builder/case-builder.schema.json) for the authoritative payload contract alongside sample fixtures such as [`sample_convergence.json`](fixtures/case_builder/sample_convergence.json) and [`sample_bundle.ndjson`](fixtures/case_builder/sample_bundle.ndjson) for end-to-end examples.

## Phase 0 – Domain model & ingestion scaffolding (Weeks 0-1)
- Introduce SQLAlchemy models and migrations for the case-builder tables—`CaseObject`, `CaseSource`, `CaseEdge`, `CaseInsight`, and `CaseUserAction`—mirroring the blueprint’s storage contract while reusing existing vector/JSON column helpers in `theo.services.api.app.db.models`.
- Extend the ingestion pipeline so every newly normalized document/passage/annotation also yields a persisted `CaseObject` with OSIS ranges, modality, and embeddings, wiring this into the existing parser/persistence flow in `ingest.pipeline`.
- Emit Postgres `NOTIFY` events on case-object upserts and register a Celery task stub (e.g., `on_case_object_upsert`) inside `theo.services.api.app.workers.tasks` to enqueue downstream scoring work, matching the worker skeleton from the blueprint.
- Add configuration flags (API + web) for staged rollout via `Settings` so the feature can be toggled per environment before exposing new routers/UI.
- Seed migration smoke tests and model validation checks to guarantee the new schema, embeddings, and signals ingest correctly from day one.

## Phase 1 – Minimal convergence insights (Weeks 1-2)
- Implement the phase-one scoring loop inside the new worker: load top-K neighbors from pgvector, compute cosine similarity plus diversity/recency features, and emit `Convergence` insights once thresholds are hit, aligning with the M1 milestone scope.
- Persist generated insights and user actions through the newly added tables so downstream consumers can query and act on them.
- Add a FastAPI router (e.g., `routes/insights.py`) with list/detail/action endpoints plus a WebSocket stub, and register it in `main.py` next to existing route groups.
- Build a minimal Next.js insight feed (list + Accept/Snooze controls) and mount it near the research experience, reusing the research layout conventions while gating by the new feature flag.
- Author unit and integration tests for ingestion→worker→API, plus React tests for the feed shell, following the repository’s existing FastAPI and Jest patterns.

## Phase 2 – Graph-derived signals & explainability (Weeks 3-4)
- Populate the `CaseEdge` graph on every candidate evaluation, computing Adamic-Adar, local clustering coefficient, Jaccard, PMI, and diversity flags, then persist feature payloads for reuse.
- Upgrade the scoring function to Reciprocal Rank Fusion across semantic/graph/association lists and feed the enriched feature bundle into the insight payload.
- Extend API serializers to include “Why it fired” explainers and neighborhood snapshots, and render matching explainer bars/graph previews in the web UI.
- Add property-based tests that assert monotonicity when source diversity increases, plus snapshot/golden tests that pin known convergence examples.

## Phase 3 – Collision detection & feedback personalization (Weeks 5-6)
- Layer contradiction heuristics (polarity checks, contradiction edges, manual annotations) on top of the scoring gate to emit `Collision` insights alongside convergences.
- Capture Accept/Snooze/Mute/Bundle actions from the UI, persist them, and feed a periodic retraining job (start with the lightweight reranker helper) to tune per-mode weights.
- Expand the insight feed with action buttons, mute controls, and mode-aware thresholds so analysts can steer results in real time.
- Add regression tests for collision-specific heuristics, per-mode scoring deltas, and action handling on both API and UI layers.

## Phase 4 – Surprise metrics, momentum & bundling (Weeks 7-8)
- Implement Bayesian surprise tracking and multi-day momentum aggregation, boosting clusters into `Bundle` insights when diverse sources contribute over time.
- Surface bundles, heatmaps, and topic muting in the UI along with timeline views so researchers can spot emerging patterns quickly.
- Instrument dashboards and alerts (accept rate, false positives, time-to-insight) to close the loop with operations and research stakeholders.
- Run targeted A/B experiments comparing default thresholds versus personalized weights, capturing Accept@K and TTI metrics as outlined in the test strategy.

## Cross-cutting launch readiness
- Publish developer and analyst documentation describing data contracts, scoring tunables, and operational runbooks alongside the case builder deliverables.
- Ensure the monitoring stack covers worker throughput, ANN index health, and feedback ingestion so maintenance teams can diagnose drift quickly.
