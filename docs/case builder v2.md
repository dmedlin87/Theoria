# Case Builder Buddy (Convergence Triggers) – Phased Implementation Plan

## Phase 0 – Discovery & Alignment (≈0.5 week)
- Validate the shared understanding of the target outcomes, covered object types, and multi-signal inputs (semantic, graph, diversity, temporal, stability) with product, data, and UX partners.
- Confirm scope for convergence, collision, lead, and bundle insight categories and how each will appear in the roadmap deliverables and acceptance criteria.
- Define success metrics (accept rate, false positives, time-to-insight) and monitoring expectations up front to guide later observability work.

## Phase 1 – Data Foundations & Ingestion (≈1–2 weeks)
- Design the Postgres schema (objects, sources, edges, insights, user_actions) plus required pgvector and B-tree/GiST indexes; produce and land migrations.
- Stand up ingestion parsers that normalize heterogeneous evidence into canonical objects, populate metadata (OSIS ranges, modality, tags), and push Postgres NOTIFY events.
- Implement embedding generation (primary + optional aspect embeddings) and HNSW index maintenance in pgvector for each upserted object.
- Establish Celery/Redis worker scaffolding triggered by Postgres events, ensuring observability around queue depth and failures.
- **Exit criteria:** migrations reviewed, ingestion+embedding pipeline processes sample data end-to-end, vector index benchmarks acceptable, notifications reach workers.

## Phase 2 – Baseline Convergence Detection & UI Skeleton (≈1–2 weeks)
- Build neighbor search feature extraction (similarity, overlap, diversity, recency, stability) to generate candidate pairs from pgvector queries.
- Implement minimal convergence scoring using similarity + diversity + recency gates, including configurable thresholds and cluster spam protections.
- Deliver the initial insight worker that emits convergence records and stores them in the insights table; ensure payloads capture rationale snippets for UI.
- Ship the minimal insight card UI with Accept/Snooze controls, source/modality badges, and OSIS chips wired through the API surface.
- **Exit criteria:** baseline convergence insights appear in UI from seeded data, Accept/Snooze actions persist, performance budget holds for top-K searches.

## Phase 3 – Graph Signals & Explainability (≈2 weeks)
- Extend pipeline to maintain property-graph edges and compute Adamic–Adar, local clustering coefficient deltas, Jaccard on tags, and PMI association features during candidate evaluation.
- Integrate Reciprocal Rank Fusion across semantic, graph, and association signals; add cluster-level lift boosts and thresholds.
- Surface “Why this fired” explainers in the insight UI, showing top features and graph context to build user trust.
- **Exit criteria:** fusion scoring validated against golden examples, explainers visible in UI, QA sign-off on determinism and signal ordering.

## Phase 4 – Collision Detection & Adaptive Feedback (≈2–3 weeks)
- Layer in contradiction heuristics (negation patterns, polarity labels, explicit contradiction edges) to emit Collision insights with tailored messaging.
- Capture user actions (accept, snooze, discard, pin) and persist them for training, enabling per-mode (Apologetic/Neutral/Skeptical) weight presets and retraining cadence.
- Expose full insight detail view, action endpoints, and debugging route for score breakdowns via FastAPI and WebSocket stream updates.
- **Exit criteria:** collision alerts demonstrably fire on curated contradictory corpora, feedback loop stores events, per-mode thresholds configurable.

## Phase 5 – Advanced Triggers & Bundled Insights (≈2 weeks)
- Implement Bayesian Surprise calculations over topic priors and hook into scoring, with accompanying visualizations (heatmaps) and filters.
- Track temporal momentum from independent sources to create bundle insights with richer write-ups and topic muting controls.
- **Exit criteria:** surprise/momentum metrics demonstrably influence ranking, bundled insights render with aggregate narratives, mute flows persist.

## Phase 6 – Production Readiness, QA, and Observability (runs alongside later phases)
- Build comprehensive test harnesses: unit coverage for feature extractors, property-based checks on source diversity monotonicity, golden corpora, and A/B scaffolding for threshold tuning.
- Harden background job operations: rate limits, retries, health dashboards, and instrumentation for accept rate/TTI KPIs.
- Finalize documentation, schema references, worker library guides, UI usage docs, and operational runbooks to satisfy the deliverable checklist.
- Gate production release behind load tests, data privacy review, and security sign-off on APIs/WebSocket endpoints.

## Timeline Reference
- The phases align with the documented milestone cadence: M1 (skeleton) 1–2 weeks, M2 (graph signals) 2 weeks, M3 (collisions/feedback) 2–3 weeks, M4 (surprise/bundles) 2 weeks; adjust for Phase 0 planning and Phase 6 readiness tasks interleaved through later milestones.
