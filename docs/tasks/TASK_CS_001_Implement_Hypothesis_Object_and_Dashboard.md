# TASK CS-001: Implement Hypothesis Object & Dashboard

**Priority**: ⭐⭐⭐ High
**Estimated Time**: 2-3 days
**Dependencies**: Research service containerization complete; analytics pipeline stable
**Status**: Ready to start

---

## 🎯 Objective

Deliver a production-ready hypothesis aggregate and surface it through a dedicated Cognitive Scholar dashboard. The task spans
domain modeling, persistence, service orchestration, API exposure, and the Next.js experience so that the research agents and
humans see the same structured view.

---

## 📋 Why This Matters

1. **Unlocks multi-hypothesis workflows** – downstream Cognitive Gate and Debate features rely on persisted hypotheses with
   supporting/contradicting evidence links.
2. **Shared contract for humans & agents** – aligns agent generated hypotheses with the UI representation and API payloads.
3. **Foundation for evaluation** – the dashboard becomes the anchor for telemetry, debate verdicts, and confidence tracking.
4. **Improves operability** – persistence + API allows auditing, replaying tests, and regression testing of reasoning outputs.

---

## 📂 Target Files / Components

- `theo/domain/research/entities.py` – promote `Hypothesis` / `HypothesisDraft` into their own module or expand with
  Cognitive Scholar metadata (trail linkage, evaluation stats, evidence counts).
- `theo/domain/repositories/hypotheses.py` – ensure the repository contract supports filtering by status/confidence/query and
  bulk operations needed by the dashboard.
- `theo/adapters/persistence/models.py` & new `theo/adapters/persistence/hypothesis_repository.py` – SQLAlchemy model + mapper
  for hypotheses, including JSONB columns for perspective scores and structured evidence references.
- `theo/application/research/service.py` – wire the repository into `ResearchService` and expose list/create/update entry
  points with validation.
- `theo/services/api/app/research/hypotheses/__init__.py` (new) – FastAPI router providing `GET /research/hypotheses`,
  `POST /research/hypotheses`, and `PATCH /research/hypotheses/{id}` endpoints returning dashboard-ready DTOs.
- `theo/services/web/app/research/hypotheses/client.ts` & `page.tsx` – connect to the new API contract, hydrate initial data,
  and render status/confidence summaries in `HypothesesDashboardClient.tsx`.
- `theo/services/web/tests/app/research/hypotheses-dashboard.test.tsx` – extend coverage for the new API payload shapes and
  interactions.
- `theo/services/api/tests/research/test_hypotheses.py` – acceptance coverage for repository + API wiring.

---

## ✅ Acceptance Criteria

- Hypotheses persist with claim text, confidence, status, supporting/contradicting passage IDs, perspective scores, and audit
  timestamps.
- API returns paginated results with filter support (`statuses`, `min_confidence`, free-text `query`).
- Dashboard lists hypotheses, allows status/confidence edits, and shows counters without console/runtime errors.
- Unit + integration tests cover repository CRUD + API surfaces + dashboard interactions.
- Documentation updated in `docs/ROADMAP.md` to link to the dashboard feature flag/URL.

---

## 🔄 Related Tasks

- **[TASK_CS_002](TASK_CS_002_Wire_Cognitive_Gate_v0.md)** – consumes the hypothesis contract for gating decisions.
- **[TASK_CS_003](TASK_CS_003_Ship_Debate_v0.md)** – depends on hypotheses being persisted + exposed on the dashboard.
