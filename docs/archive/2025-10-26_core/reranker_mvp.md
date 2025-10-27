> **Archived on 2025-10-26**

# Reranker & Intent Tagger MVP

## Goals
- Improve hybrid retrieval quality by inserting a lightweight ML reranker between dense/sparse scoring and response generation.
- Capture user intent classifications to steer downstream prompting, analytics, and routing while remaining privacy conscious.
- Ship behind feature flags so production defaults remain deterministic until offline metrics and manual QA clear the launch gates.

## Feature Flags & Configuration
- `RERANKER_ENABLED` — gate the ONNX reranker execution. Defaults to `0` in `.env.example` so only opt-in environments activate it.
- `RERANKER_MODEL_PATH` — filesystem path to the exported reranker artifact. Use local relative paths (e.g. `./models/reranker/model.onnx`) for development.
- `INTENT_TAGGER_ENABLED` — guardrail for the intent classifier. Disabled by default to prevent accidental rollout.
- `INTENT_MODEL_PATH` — location of the serialized intent tagger (ONNX or TorchScript). Stored alongside reranker assets under `./models/intent/` by convention.

## Training Pipeline Overview
1. **Curate datasets**
   - Reranker: export hybrid search traces and analyst-labeled relevance judgements to `data/training/reranker/*.jsonl`.
   - Intent tagger: collect anonymised query transcripts with human-tagged intents in `data/training/intent/*.jsonl`.
2. **Feature engineering**
   - Use scikit-learn pipelines (`requirements.txt`) to normalise embeddings, lexical scores, and contextual signals.
   - Persist intermediate datasets with `joblib` for reproducibility.
3. **Model training commands**
   - Reranker: `python -m theo.experiments.reranker.train --config configs/reranker.yaml`
   - Intent tagger: `python -m theo.experiments.intent.train --config configs/intent.yaml`
4. **Artifact export**
   - Convert the fitted estimators to ONNX via `skl2onnx` or direct joblib serialisation with conversion during deployment.
   - Store exported models under `models/` with semantic version folders (e.g. `models/reranker/v0/model.onnx`).
5. **Versioning**
   - Tag each artifact with Git SHA + dataset snapshot hash.
   - Update release notes with the experiment configuration and validation metrics.

## Evaluation & Benchmarks
- Use the existing RAG evaluation CLI to capture before/after metrics:
  ```bash
  python -m theo.infrastructure.cli.rag_eval --dev-path data/eval/rag_dev.jsonl \
    --trace-path data/eval/production_traces.jsonl \
    --output data/eval/reranker_candidate.json
  ```
- Record deltas for `faithfulness`, `groundedness`, `context_precision`, `context_recall`, and `answer_relevance`.
- Extend the bench script with reranker/intent checkpoints to ensure regressions fail CI when tolerances are exceeded.
- Validate intent accuracy via stratified hold-out splits:
  ```bash
  python -m theo.experiments.intent.evaluate --split validation --report reports/intent_eval.json
  ```

## Deployment & Rollback
1. Publish artifacts to the shared storage bucket with immutable version folders.
2. Update environment variables in staging to point at the new paths.
3. Enable `RERANKER_ENABLED=1` and `INTENT_TAGGER_ENABLED=1` in staging, run CI + bench scripts, and conduct manual smoke tests.
4. Roll out to production via feature flag toggles after validating telemetry.
5. Rollback strategy: flip flags back to `0`, redeploy configuration, and invalidate caches. Keep previous artifacts in place for quick reversion.

## Telemetry Expectations
- Emit Prometheus counters for reranker/intent invocations and latency histograms to detect performance regressions.
- Log per-request confidence scores (capped/anonymised) to feed weekly drift dashboards.
- Capture toggles in structured logs so observability systems can correlate incidents with flag state changes.
- Ensure evaluation summaries (`data/eval/latest_results.json`) are archived per release for auditability.
