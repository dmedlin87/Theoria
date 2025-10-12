# Theoria – Case Builder Buddy: Convergence Triggers Blueprint

## Goal
Detect “data convergence” moments—when independent items (Evidence Cards, citations, verses, transcripts, notes) begin to align in meaning or implication—and surface them as actionable insights with traceable rationale.

---

## Core Concepts
- **Objects**: `EvidenceCard`, `Claim`, `Citation`, `Source`, `VerseRef` (OSIS), `Annotation`, `UserAction` (accept/snooze/pin), `Contradiction`, `Topic`.
- **Signals**: (a) semantic similarity, (b) graph topology change, (c) co‑occurrence/association, (d) surprise/novelty, (e) source diversity, (f) temporal momentum, (g) stability ratings.
- **Outcomes**: `Convergence` (supportive alignment), `Collision` (meaningful contradiction), `Lead` (follow‑up suggestion), `Bundle` (auto‑grouped insight packet).

---

## Data Model (Postgres + pgvector + property graph)

### Tables (simplified)
- `objects(id, type, title, body, osis_ranges[], modality, source_id, created_at, published_at, stability, tags[], embedding vector)`
- `sources(id, origin, author, year, url, modality)`
- `edges(src_id, dst_id, kind, weight, features jsonb, created_at)`  
  *kinds:* `semantic_sim`, `co_citation`, `verse_overlap`, `topic_overlap`, `contradiction`.
- `insights(id, type, score, payload jsonb, created_at, cluster_id)`
- `user_actions(id, insight_id, action, confidence, created_at)`

### Indexes
- `embedding` column: HNSW (primary); optionally IVF for batch insert heavy phases.  
- B‑tree/GiST on `osis_ranges`, `tags`, `created_at`.

### Event Bus
- Postgres `NOTIFY` on new/updated `objects` → Celery/worker queue.

---

## Pipeline Overview

1. **Ingest**  
   Parsers normalize to `objects`. Extract:
   - clean text, OSIS ranges, lemmas/keywords, modality (Transcript, PDF, Book, Note, Verse), source metadata.

2. **Embed**  
   Generate primary text embedding + optional aspect embeddings (claim‑only, verse‑only, citation‑only). Store in `embedding`. Upsert HNSW.

3. **Neighborhood Search**  
   On insert/update, query top‑K neighbors from pgvector. Build candidate pairs `(new, neighbor)` with features:
   - cosine similarity
   - verse/lemma overlap
   - source independence (author/origin distinct?)
   - modality diversity
   - recency deltas
   - stability weighted average

4. **Graph Update**  
   Create/refresh `edges` with `features`. Maintain local caches for cluster metrics (e.g., triangle counts, local clustering coefficient, modularity bucket).

5. **Score & Classify**  
   Compute multi‑signal score (see formula below). If threshold crossed, emit `insights` of type `Convergence` or `Collision` with an explainer payload.

6. **Feedback Loop**  
   User marks Accept/Snooze/Discard; store as training data. Periodically retrain weights (logistic/GBDT) and thresholds per *mode* (Apologetic/Neutral/Skeptical).

---

## Convergence Scoring (V1)

Let candidate neighbors for new object `o` be `N_topK`. For each `n ∈ N_topK`, compute:

- **Semantic**: `sim = cosine(o.embedding, n.embedding)`
- **Graph**:
  - `aa = Adamic–Adar(o,n)` on the topical graph
  - `lcc_Δ = Δ(local clustering coefficient)` if edge(o,n) added
  - `jacc = Jaccard(tags(o), tags(n))`
- **Association**:
  - `pmi = PMI(term_set(o), term_set(n))` (with floor/clip)
- **Diversity**:
  - `mod_div = 1` if modality(o) ≠ modality(n) else `0`
  - `src_div = 1` if source(o).author != source(n).author else `0`
- **Temporal**:
  - `recency = exp(-Δt / τ)` (τ in days)
- **Stability**:
  - `stab = min(stability(o), stability(n))`

**Rank‑fusion**: produce ranked lists by each signal (`sim`, `aa`, `pmi`, `lcc_Δ`) and combine with Reciprocal Rank Fusion.  
`score_pair = RRF(sim, aa, pmi, lcc_Δ) * (0.25 + 0.15*jacc + 0.15*mod_div + 0.15*src_div + 0.15*recency + 0.15*stab)`  
Aggregate to an object‑level score via `max(score_pair)` and a cluster‑level boost if multiple neighbors exceed a mini‑threshold in a sliding window (e.g., last 7 days).

**Fire** `Convergence` when:
- `score ≥ τ_conv` **and** at least one of {`mod_div`, `src_div`} = 1  
- **and** `lcc_Δ` lifts local cluster above percentile P (to avoid spam)

**Fire** `Collision` when:
- `score ≥ τ_col` **and** contradiction heuristics fire (negation patterns, opposite polarity labels, or manual `Contradiction` edges)

---

## “Surprise” & Momentum (V2+)
- Maintain a prior over topic distributions per cluster. Compute **Bayesian Surprise** for new evidence (KL divergence between prior and posterior). Use as an additional ranker and for *Insight Heatmaps* over time.
- Track **momentum**: consecutive days with non‑overlapping sources contributing to the same cluster → escalate to `Bundle` with a richer write‑up.

---

## Worker Pseudocode (V1)
```python
@task
def on_object_upsert(object_id):
    o = fetch_object(object_id)
    ensure_embedding(o)
    nbrs = ann_search(o.embedding, k=64)

    candidates = []
    for n in nbrs:
        feats = compute_features(o, n)
        pair_score = score_pair(feats)
        if pair_score > PAIR_MIN:
            candidates.append((n.id, feats, pair_score))

    if not candidates:
        return

    cluster_metrics = compute_cluster_effects(o, candidates)
    final_score = combine_candidates(candidates, cluster_metrics)

    if is_convergence(final_score, candidates, cluster_metrics):
        emit_insight("Convergence", o, candidates, cluster_metrics)
    elif is_collision(final_score, candidates, cluster_metrics):
        emit_insight("Collision", o, candidates, cluster_metrics)
```

---

## UX Spec (Insight Feed)
- **Insight Card**: title, 2–3 key snippets, *Why this fired* explainer (top signals with mini‑bars), sources & modalities badges, OSIS chips, *Open Graph* button.
- **Controls**: Accept → create/merge `EvidenceCard`; Snooze (7d/30d); Mute topic; Promote to `Bundle`.
- **Explainers**: show `sim`, `aa`, `lcc_Δ`, `pmi`, source/modality diversity, recency, stability. Link to a *diff‑style* view of how the cluster changed.
- **Feed Filters**: mode (Apologetic/Neutral/Skeptical), topic, source, min‑score, timeframe.

---

## API Endpoints (FastAPI)
- `GET /insights?since=<ts>&type=convergence|collision|bundle&min_score=`
- `GET /insights/{id}` (full payload, graph neighborhood, explainer)
- `POST /insights/{id}/action` (accept/snooze/pin/discard)
- `WS /insights/stream` (server‑push on new insights)
- `GET /debug/score?object_id=` (features and fusion breakdown)

---

## Background Jobs & Infra
- **Eventing**: Postgres `LISTEN/NOTIFY` on `objects_changed` → worker
- **Workers**: Celery + Redis broker; rate‑limit per user/project
- **ANN**: pgvector HNSW index; nightly auto‑vacuum/analyze; optional IVF for bulk loads
- **Modeling**: periodic weight tuning using user feedback (logistic regression or GBDT)
- **Monitoring**: metrics on accept rate, false‑positive rate, time‑to‑first‑insight; Grafana dashboards

---

## Milestones
**M1 – Skeleton (1–2 weeks)**
- Tables, embeddings, HNSW, basic neighbor search
- Thresholded `Convergence` on `sim + diversity + recency`
- Minimal Insight Card + Accept/Snooze

**M2 – Graph Signals (2 weeks)**
- Property graph derivation; Adamic–Adar, local clustering coefficient; Jaccard on tags
- Rank‑fusion scoring + explainers

**M3 – Collisions & Feedback (2–3 weeks)**
- Contradiction heuristics & `Collision` insights
- Per‑mode weight presets; user feedback → retraining loop

**M4 – Surprise & Bundles (2 weeks)**
- Bayesian Surprise & momentum tracker
- Bundled write‑ups, heatmaps, topic muting

---

## Test Plan (High‑Signal)
- **Unit**: feature extractors, rank‑fusion determinism, OSIS overlap logic
- **Property‑based**: random graphs → verify monotonicity (more independent sources → higher score)
- **Golden Sets**: handcrafted mini‑corpus with known convergences/collisions
- **A/B**: default thresholds vs personalized weights → Accept@10, TTI (time‑to‑insight)

---

## Notes & Variants
- Can maintain a small *ensemble* of embeddings (general, verse‑aware, citation‑aware) and fuse via RRF to reduce brittleness.
- To reduce spam, add *cooldowns* per cluster and per source.
- Consider a **Lead** type when score is mid‑range but diversity is high—good for prompting research without claiming convergence.

---

## Deliverables
- Schema migration SQL
- Worker + feature library
- Insight Feed UI (Next.js 14): list, detail, graph mini‑map, explainers
- Documentation: scoring spec with tunables; dashboard with metrics

