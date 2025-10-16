# Case Builder v1 Plan

## Phase 1 – Data & Ingestion Foundation
- Ship core Postgres schema for objects, sources, edges, insights, and user actions with pgvector support and the required indexes/NOTIFY hooks to drive downstream workers.
- Build ingestion parsers that normalize heterogeneous inputs into the canonical `objects` table while extracting text, OSIS ranges, modality, linguistic features, and source metadata.
- Generate primary embeddings (plus optional aspect variants) and populate the HNSW index; create the Celery worker skeleton that ensures embeddings exist and kicks off neighborhood search on each upsert.
- Deliver a minimal FastAPI surface (`GET /insights`, `GET /insights/{id}`) and a lightweight Insight Card UI with Accept/Snooze controls to expose first convergence events driven by simple similarity + diversity + recency heuristics.

**Exit criteria:** Independent evidence items can be ingested, embedded, matched by similarity/diversity, and surfaced through the feed with baseline explainers.

## Phase 2 – Graph-Enriched Scoring & Explainability
- Populate property-graph edges, derive Adamic–Adar, local clustering coefficient, Jaccard, PMI, and diversity metrics for candidate pairs, and feed them into the reciprocal-rank fusion scoring pipeline.
- Expand insight explainers to visualize top signals, diversity, and cluster lift, and surface graph context in the detail view to help analysts interpret triggers.
- Harden worker performance with caching of cluster metrics and ensure ANN queries scale; add dashboards for throughput, latency, and insight fire rates.

**Exit criteria:** Convergence scoring incorporates multi-signal fusion with transparent explainers, and operations have visibility into worker health.

## Phase 3 – Collision Detection & Feedback Personalization
- Implement contradiction heuristics and explicit `Contradiction` edges so the worker can fire `Collision` insights when high-scoring pairs disagree meaningfully.
- Capture user actions (accept, snooze, discard, pin) via the API, store them in `user_actions`, and incorporate them into feedback-driven weight tuning per investigative mode (Apologetic/Neutral/Skeptical).
- Extend the Insight Feed with filters by mode, topic, source, and timeframe; expose debugging endpoints for score breakdowns and contradiction rationale.

**Exit criteria:** Collision insights are available, analysts can adjust perspectives via modes, and the system learns from user feedback.

## Phase 4 – Advanced Signals, Bundling, and Monitoring
- Introduce Bayesian surprise and temporal momentum calculations to highlight unexpected contributions and multi-day convergence, promoting qualifying clusters into bundles with richer narratives.
- Support `Bundle` outcomes in the API/UI with heatmaps, topic muting, and graph previews; enable lead suggestions for mid-score high-diversity events to encourage research follow-up.
- Finalize operational dashboards to monitor accept rate, false positives, and time-to-insight, and schedule periodic model retraining jobs driven by accumulated feedback.

**Exit criteria:** Analysts receive advanced convergence intelligence, bundles, and leads with full observability and adaptive modeling.

## Quality & Testing Strategy
- Throughout phases, implement unit tests for feature extractors, ranking fusion, and OSIS overlap; add property-based tests for diversity monotonicity, golden datasets for regression, and plan A/B experiments comparing threshold presets to personalized weights.
- Document scoring tunables, worker operations, and UI usage, and ensure schema migrations and worker libraries are versioned for deployment readiness.

## Testing
⚠️ `tests not run (read-only analysis mode)`
