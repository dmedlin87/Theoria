# Case Builder Buddy – Convergence Triggers Blueprint Summary

> **Latest Case Builder spec:** [`case builder v4.md`](../case%20builder%20v4.md)

This summary highlights the convergence trigger blueprint at a glance; refer to the linked spec for the authoritative, versioned requirements.

## Objective
The system detects when independently sourced theological evidence begins to align or diverge, producing actionable insights that cite their supporting rationale and provenance.

## Key Entities and Signals
- Objects include evidence cards, claims, citations, sources, OSIS verse references, annotations, user actions, contradictions, and topics.
- Signals feeding the insight engine measure semantic similarity, graph topology changes, co-occurrence strength, surprise, source diversity, temporal momentum, and stability ratings.
- Outcomes categorize surfaced events as convergence, collision, lead suggestions, or bundled insight packets.

## Storage Model
- Postgres with pgvector stores normalized objects and sources, maintains feature-rich edges between objects, and persists generated insights and user actions.
- HNSW vector indexes accelerate embedding searches, while B-tree or GiST indexes cover OSIS ranges, tags, and timestamps.
- Postgres NOTIFY events drive downstream processing workers.

## Processing Pipeline
1. **Ingest:** Parsers normalize heterogeneous inputs, extract text, OSIS ranges, linguistic features, modality, and source metadata.
2. **Embed:** Generate core and optional aspect embeddings, then upsert them into pgvector.
3. **Neighborhood Search:** Query top-K neighbors and compute pairwise features such as similarity, overlap, diversity, recency, and stability.
4. **Graph Update:** Maintain property-graph edges with feature payloads and local cluster metrics.
5. **Score & Classify:** Fuse multi-signal scores and emit convergence or collision insights when thresholds and diversity constraints are met.
6. **Feedback Loop:** Capture user actions to retrain weights per analysis mode and refine thresholds.

## Convergence & Collision Logic
- Pair scoring combines semantic, graph-based, association, and diversity features via Reciprocal Rank Fusion, modulated by tag overlap, modality/source diversity, recency decay, and stability.
- Convergence fires when scores clear a tuned threshold, diversity requirements, and cluster lift conditions; collision triggers add contradiction heuristics atop the score gate.

## Advanced Signals
- Bayesian surprise augments ranking by measuring deviations from cluster topic priors, while momentum tracks multi-day contributions from independent sources to justify bundled insights.

## Worker Skeleton
A Celery task responds to object upserts by ensuring embeddings, searching neighbors, filtering candidates, computing cluster effects, and emitting insights for qualifying convergence or collision events.

## Insight Feed Experience
Insight cards summarize triggers with explainer bars, show source/modality badges and OSIS chips, and offer actions to accept, snooze, mute, or bundle. Filters support investigative modes, topics, sources, score floors, and time windows.

## API Surface
REST and WebSocket endpoints expose insight listings, detail views with graph context, action submission, and debugging of score breakdowns.

## Infrastructure & Monitoring
Workers consume Postgres notifications via Celery, Redis brokers coordinate jobs, pgvector handles ANN search, and periodic model tuning leverages feedback. Monitoring tracks accept rates, false positives, and time-to-insight through dashboards.

## Delivery Roadmap
- **M1:** Core storage, embeddings, neighbor search, and minimal convergence insights with basic UI controls.
- **M2:** Graph-derived signals and explainers.
- **M3:** Collision detection and feedback-driven personalization.
- **M4:** Surprise metrics, momentum bundles, and richer visualization tooling.

## Testing Approach
Unit tests cover feature logic, property-based tests validate monotonicity around source diversity, golden sets anchor known cases, and A/B experiments compare threshold presets against personalized weights.

## Deliverables
Required artifacts span schema migrations, the worker and feature computation library, a Next.js insight feed with explainers and graph previews, and documentation plus operational dashboards.
