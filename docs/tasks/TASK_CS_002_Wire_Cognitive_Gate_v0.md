# TASK CS-002: Wire Cognitive Gate v0

**Priority**: ⭐⭐⭐ High
**Estimated Time**: 3-4 days
**Dependencies**: CS-001 merged (shared hypothesis contract); tracing exporter configured
**Status**: Blocked by CS-001

---

## 🎯 Objective

Stand up a first-pass Cognitive Gate that mediates high-cost reasoning workflows. The gate should introspect prompt/response
entropy, citation coverage, and hypothesis alignment before allowing the router to execute an expensive generation.

---

## 📋 Why This Matters

1. **Protects budget** – stops runaway loops when the agent lacks citations or repeats high entropy drafts.
2. **Improves rigor** – enforces minimum evidence coverage before hypotheses advance status.
3. **Feeds analytics** – produces structured gate verdicts for dashboards and alerts.
4. **Unlocks Debate & Autonomy** – future orchestration (Debate v0, Detective→Critic loop) depends on this guardrail layer.

---

## 📂 Target Files / Components

- `theo/services/api/app/ai/router.py` – inject gate checks prior to `execute_generation`, short-circuiting requests that fail
  policy and emitting structured rejection reasons.
- `theo/services/api/app/ai/gate.py` (new) – encapsulate heuristics for entropy (Shannon score from token probabilities),
  citation coverage (references pulled from `rag.retrieval` results), and hypothesis alignment (compare against
  `Hypothesis` records via `ResearchService`).
- `theo/services/api/app/ai/audit_logging.py` – log Cognitive Gate decisions with correlation IDs and latency metrics.
- `theo/application/reasoner/events.py` – publish `CognitiveGateVerdict` events consumed by orchestrators.
- `theo/services/api/app/ai/registry.py` – expose configuration toggles (`cognitive_gate.enabled`, thresholds, bypass roles).
- `theo/services/api/tests/research/test_hypotheses.py` & `theo/services/api/tests/test_ai_routes.py` – add coverage for gate
  acceptance/rejection paths, ensuring hypotheses without citations are blocked until evidence arrives.
- `docs/agents/thinking-enhancement.md` – document the new gate flow and configuration knobs.

---

## ✅ Acceptance Criteria

- Cognitive Gate intercepts research workflows (`workflow="research.autonomous"` + `"research.debate"`) with configurable
  thresholds for entropy and citation coverage.
- Gate verdicts are recorded to structured logs and OpenTelemetry spans, including reasons and remediation hints.
- Router gracefully falls back to cheaper models or returns actionable errors when the gate denies execution.
- Research orchestrators receive gate events and adjust their plan (e.g., request more citations) without crashing.
- Unit + integration tests cover permit/deny scenarios with deterministic fixtures.

---

## 🔄 Related Tasks

- **[TASK_CS_001](TASK_CS_001_Implement_Hypothesis_Object_and_Dashboard.md)** – supplies the hypothesis/evidence data the gate
  verifies.
- **[TASK_CS_003](TASK_CS_003_Ship_Debate_v0.md)** – relies on gate verdicts to decide when debates can proceed.
