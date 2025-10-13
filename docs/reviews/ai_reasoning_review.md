# AI Reasoning Module Review

## Overview
The reasoning package combines prompt scaffolding, post-hoc critique, fallacy detection, hypothesis generation, insight discovery, and perspective synthesis for the theological agent workflows. The code relies on lightweight dataclasses and heuristics to keep outputs structured and reviewable while routing LLM calls only when needed.【F:theo/services/api/app/ai/reasoning/chain_of_thought.py†L13-L198】【F:theo/services/api/app/ai/reasoning/hypotheses.py†L125-L244】

## Strengths
- **Well-structured prompts and data models.** Prompt builders cover multiple reasoning personae and explicitly guide the model through numbered steps, which makes later parsing feasible. Dataclasses such as `ReasoningStep` and `ChainOfThought` capture the chain-of-thought output in a deterministic form.【F:theo/services/api/app/ai/reasoning/chain_of_thought.py†L13-L200】
- **Layered fallback strategies.** Hypothesis generation first tries router-driven LLM calls but gracefully falls back to heuristic extraction from passages or traces so the system still produces candidates under failure conditions.【F:theo/services/api/app/ai/reasoning/hypotheses.py†L125-L244】
- **Perspective synthesis pipeline.** The perspective module standardizes retrieval filters per stance, extracts key claims, and composes meta-analysis that highlights consensus and tensions—useful scaffolding for downstream UI or audits.【F:theo/services/api/app/ai/reasoning/perspectives.py†L55-L259】

## Issues to Address
1. **Formal fallacy pattern never executes.** `AFFIRMING_CONSEQUENT` is defined but omitted from `FALLACY_PATTERNS`, so this formal fallacy can never be detected. The fix is to add the pattern to the list (and optionally a suggestion string).【F:theo/services/api/app/ai/reasoning/fallacies.py†L24-L166】
2. **Insight IDs are nondeterministic.** `_detect_cross_references` uses Python's salted `hash()` to derive an ID suffix, meaning identifiers change between interpreter runs and can collide unpredictably. Persisted insight references or cache keys would therefore be unstable; swap to a deterministic hash (e.g., `hashlib.sha1`) or structured ID.【F:theo/services/api/app/ai/reasoning/insights.py†L105-L139】
3. **Critique quality can fall below zero.** After clamping for fallacy penalties, additional deductions for weak citations and bias can drive `reasoning_quality` negative even though the dataclass documents a 0–100 scale. Apply a final clamp before returning to keep scores in range.【F:theo/services/api/app/ai/reasoning/metacognition.py†L59-L109】

## Additional Opportunities
- **Populate alternative interpretations.** The critique model exposes an `alternative_interpretations` list, but no analyzer currently fills it, so API consumers always receive an empty array. Consider mining reasoning traces for explicit alternative readings or flagging TODOs for future expansion.【F:theo/services/api/app/ai/reasoning/metacognition.py†L35-L109】
- **Reduce false contradiction flags.** `_classify_passage_evidence` treats common discourse markers like "however" or "but" as contradictions, which can mislabel supporting material in longer snippets. Tightening the heuristic (e.g., require overlap with negated claim terms) would improve signal-to-noise, especially for downstream confidence updates.【F:theo/services/api/app/ai/reasoning/hypotheses.py†L715-L750】
- **Stabilize perspective consensus detection.** `_find_common_ground` intersects full sentence strings, so minor phrasing differences across perspectives prevent consensus from surfacing. Normalizing claims (lowercasing, trimming punctuation, or semantic clustering) would yield more meaningful intersections.【F:theo/services/api/app/ai/reasoning/perspectives.py†L245-L307】

## Suggested Next Steps
1. Wire the affirming-consequent detector into `FALLACY_PATTERNS` and extend `_get_suggestion` to keep messaging consistent.【F:theo/services/api/app/ai/reasoning/fallacies.py†L24-L166】
2. Replace non-deterministic insight IDs with a repeatable hash or composite key (e.g., join book codes) so insights remain stable across runs.【F:theo/services/api/app/ai/reasoning/insights.py†L105-L139】
3. Clamp critique scores post adjustments and backfill `alternative_interpretations` extraction to unlock that column in persisted critiques.【F:theo/services/api/app/ai/reasoning/metacognition.py†L35-L109】
4. Tune contradiction heuristics and consensus normalization once the above correctness fixes land, improving downstream reasoning metrics.【F:theo/services/api/app/ai/reasoning/hypotheses.py†L715-L750】【F:theo/services/api/app/ai/reasoning/perspectives.py†L245-L307】
