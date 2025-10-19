# Maturing Trend & Anomaly Detectors for Theoria

> **Status:** Research blueprint (2025-10-18)

This document distills the research plan for elevating Theoria's timeline-focused discovery engines—specifically the **trend** and **anomaly** detectors—so they reach parity with the mature **pattern** and **contradiction** detectors.

## Objective

Deliver reliable, explainable time-based theological insights by:

- Understanding the current discovery baseline and identifying the pain points affecting temporal analysis.
- Surveying temporal modelling and anomaly detection techniques that fit Theoria's hybrid symbolic/ML architecture.
- Designing experiments that measure accuracy, latency, and user trust for candidate approaches.
- Charting the integration path into the DiscoveryService pipeline, storage model, and frontend discovery cards.
- Enumerating risks (bias, performance, drift) with mitigation strategies and monitoring plans.
- Packaging outputs (reports, prototypes, roadmap) that unblock implementation work.

## 1. Baseline Assessment

### Existing Detectors

- **Pattern detector** clusters document embeddings with DBSCAN, labels clusters via shared themes/verses, and emits confidence/relevance scores capped below 1.0.
- **Contradiction detector** extracts claim sentences, evaluates pairwise relationships with a DeBERTa-v3 MNLI model, and surfaces high-probability contradictions with supporting metadata.
- Both detectors run on the APScheduler-driven `DiscoveryService` refresh loop (~30-minute cadence) with immediate reruns triggered after new ingest events.

### Timeline Pipeline Today

- Each discovery run writes a corpus snapshot (document totals, OSIS coverage, dominant topics) into `corpus_snapshots`.
- The envisioned timeline UI would diff snapshots to highlight focus changes, but sparseness, embedding jitter, and scheduler latency currently limit trustworthy insights.

## 2. Theoretical Foundations

### Temporal Modelling Techniques

- **Dynamic Topic Models (DTM):** Capture topic drift across chronological corpora; useful for progressive theological themes (e.g., Pauline emphasis shifts).
- **Temporal Word Embeddings:** Trace semantic changes in key terms ("covenant", "sacrifice") across time slices or canonical order.
- **Bayesian Changepoint Detection:** Identify statistically significant shifts in topic frequency or usage patterns with confidence intervals.
- **Classical Time-Series Analysis:** Apply moving averages, decomposition, and ARIMA/Holt-Winters to smoothed metric counts (documents, queries, verse citations).

### Anomaly Detection Paradigms

- **Density-based (DBSCAN/LOF):** Extend existing embedding pipelines to flag low-density documents/verses as outliers.
- **Probabilistic:** Model expected counts or ratios (e.g., citations per book) and flag deviations via Poisson/Gaussian thresholds.
- **Neural/Self-supervised:** Autoencoders or sequence models that learn "normal" theological vectors and flag high reconstruction or prediction errors.
- **Rule-based:** Symbolic heuristics leveraging OSIS parsing, topic ontologies, and research workflows to guarantee interpretable alerts.

### Prior Art & Benchmarks

- Digital humanities work applying topic modelling to canonical corpora provides qualitative checkpoints (OT → NT theme transitions).
- Historical/Biblical theology scholarship supplies ground-truth changepoints (e.g., Council of Nicaea) to validate timeline outputs.

## 3. Experiment Design

### Evaluation Metrics

- **Precision/Recall** against curated change events (real and synthetic).
- **Latency** from ingestion → detection (data-to-insight + compute time).
- **User-perceived accuracy** via discovery feedback (helpful/not helpful) and interviews.

### Datasets

- **High-confidence corpora:** Chronologically ordered Pauline epistles, Synoptic Gospels, or dated theological essays.
- **Synthetic scenarios:** Controlled topic distribution flips and injected outlier passages to stress-test recall/false-positive behaviour.

### Prototype Approaches

- Seasonal decomposition and statistical thresholds on aggregated metrics.
- Temporal clustering of corpus embeddings (windowed similarity, k-means, DBSCAN).
- Bayesian changepoint algorithms for topic ratios.
- Neural sequence prediction (LSTM/transformer) as exploratory baselines.

Collect precision/recall, helpfulness ratios, and runtime/memory profiles for each candidate to guide final selection or hybridization.

## 4. Integration Pathways

### Backend Pipeline

- Extend the APScheduler job and event-triggered hooks to call new `TrendDiscoveryEngine` and `AnomalyDiscoveryEngine` modules.
- Read from `corpus_snapshots` (and generate if missing) to assemble historical timelines.
- Persist new discoveries in `discoveries` with enriched `trendData`/`anomalyData` metadata (metrics, time windows, related documents/verses).

### Vector & Index Usage

- Reuse `DocumentEmbedding` entries stored via pgvector for distance-based anomaly scoring.
- Optionally maintain incremental statistics to avoid O(n²) recomputations on large corpora.

### Explanation & UX

- Author descriptive titles (e.g., "Trend detected: Rising eschatology focus") with concrete metrics and evidence lists.
- Surface confidence indicators using underlying statistical/heuristic scores.
- Ensure discovery cards, icons, and metadata schemas (`relatedDocuments`, verse citations) are wired through the API and frontend components.
- Honour existing feedback/dismiss mechanics to learn user preferences and suppress acknowledged anomalies.

## 5. Risks & Mitigations

| Risk | Impact | Mitigations |
| --- | --- | --- |
| **Theological nuance & bias** | Misclassified tensions or legitimate minority views flagged as anomalies | Human-in-the-loop review for low-confidence cases, fine-tune domain models, embed rule-based guardrails, always cite supporting evidence |
| **Latency & resource usage** | Stale timelines or sluggish refresh jobs | Incremental updates, windowed analysis, parallel execution, GPU acceleration where available, skip runs when no data changed |
| **Maintenance & drift** | Detector degradation as user behaviour evolves | Monitoring dashboards (generation rate, feedback ratio), adaptive thresholds, regression tests, modular detector code, documented configuration knobs |

## 6. Deliverables

1. **Technical report** summarising research, experiment results, and recommended architecture changes.
2. **Model comparison matrix** detailing precision/recall vs cost for each candidate detector.
3. **Updated architecture blueprint & implementation roadmap** with milestones and validation checkpoints.
4. **Prototype notebooks/scripts** demonstrating key analytics (changepoint detection, embedding clustering, anomaly scoring).
5. **Curated test datasets** (real + synthetic) for automated and manual validation.

These artefacts equip implementers to close the maturity gap and deliver dependable timeline-based discoveries.
