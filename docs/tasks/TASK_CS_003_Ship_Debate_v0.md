# TASK CS-003: Ship Debate v0

**Priority**: ⭐⭐ Medium-High
**Estimated Time**: 4-5 days
**Dependencies**: CS-001 + CS-002 complete; router streaming stable
**Status**: Blocked by CS-002

---

## 🎯 Objective

Launch a Debate v0 experience where Theo spins up two perspectives, runs a single rebuttal round, judges the outcome, and feeds
the verdict back into the hypothesis dashboard.

---

## 📋 Why This Matters

1. **Validates multi-perspective reasoning** – ensures we can hold two competing narratives and capture their evidence trails.
2. **Feeds Hypothesis confidence** – verdict deltas adjust confidence bars on the dashboard.
3. **Creates reusable orchestration pattern** – sets the stage for Debate v1 (multi-round, panel judge).
4. **Delights users** – surfaces a tangible Cognitive Scholar moment with transcripts and verdict rationales.

---

## 📂 Target Files / Components

- `theo/services/api/app/ai/reasoning/debate.py` (new) – orchestrate debate rounds using existing `LLMRouterService`, ensuring
  each side receives the same context and citing retrieved passages.
- `theo/application/reasoner/graph.py` – extend orchestration graph with a `debate_v0` node that schedules openings,
  rebuttals, and judge evaluation, emitting structured events.
- `theo/domain/research/entities.py` – add lightweight `DebateTranscript` / `DebateVerdict` dataclasses linked to
  `Hypothesis.id`.
- `theo/adapters/persistence/models.py` + new `DebateTranscriptRepository` – persist transcripts and verdict metadata so that
  verdicts can be replayed and shown on the dashboard.
- `theo/services/api/app/research/debate/__init__.py` (new) – FastAPI endpoints to trigger a debate for a hypothesis and fetch
  transcripts.
- `theo/services/web/app/research/debate/page.tsx` & supporting components – render transcript timeline, verdict summary, and a
  CTA to adjust hypothesis status/confidence.
- `theo/services/web/tests/app/research/debate-page.test.tsx` – ensure the UI handles streaming states, verdict updates, and
  empty results.
- `theo/services/api/tests/research/test_debate_routes.py` – integration tests covering happy-path debates and gate denials.
- `docs/tasks/TASK_CS_001_Implement_Hypothesis_Object_and_Dashboard.md` – cross-link so contributors know Debate updates
  the dashboard confidence.

---

## ✅ Acceptance Criteria

- Debate endpoint accepts a hypothesis ID, runs two perspectives (skeptical vs. apologetic by default), and stores opening,
  rebuttal, and judge messages with citations.
- Verdict updates hypothesis confidence/metadata and is visible within the dashboard minutes after completion.
- UI presents transcripts with streaming feedback, error states, and a verdict card referencing citations.
- Cognitive Gate integration ensures debates without sufficient evidence short-circuit with actionable errors.
- Unit/integration tests cover orchestration, persistence, API routes, and React components.

---

## 🔄 Related Tasks

- **[TASK_CS_001](TASK_CS_001_Implement_Hypothesis_Object_and_Dashboard.md)** – debate verdicts update the dashboard + hypothesis
  records.
- **[TASK_CS_002](TASK_CS_002_Wire_Cognitive_Gate_v0.md)** – gate verdicts control whether a debate can launch.
