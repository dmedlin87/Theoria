# Task Handoff Documents

This directory now tracks the Cognitive Scholar MVP backlog. Each task describes the work needed to evolve Theo into the
Cognitive Scholar experience—complete with hypotheses, guardrails, and debate orchestration.

---

## 📋 Task List

### High Priority ⭐⭐⭐

- **[TASK_CS_001](TASK_CS_001_Implement_Hypothesis_Object_and_Dashboard.md)** – Implement Hypothesis Object & Dashboard
  - Production-grade hypothesis aggregate + persistence layer
  - API + Next.js dashboard for Cognitive Scholar operators
  - **Time**: 2-3 days
  - **Status**: Ready to start

- **[TASK_CS_002](TASK_CS_002_Wire_Cognitive_Gate_v0.md)** – Wire Cognitive Gate v0
  - Guardrails for expensive reasoning workflows
  - Gate verdict events + telemetry
  - **Time**: 3-4 days
  - **Status**: Blocked by CS-001

### Medium Priority ⭐⭐

- **[TASK_CS_003](TASK_CS_003_Ship_Debate_v0.md)** – Ship Debate v0
  - Two-perspective debate orchestration with judge verdict
  - Debate transcripts + dashboard integration
  - **Time**: 4-5 days
  - **Status**: Blocked by CS-002

---

## 🎯 Recommended Order

1. **TASK_CS_001** – Establish hypothesis data contracts and dashboard.
2. **TASK_CS_002** – Layer Cognitive Gate heuristics on top of the new contracts.
3. **TASK_CS_003** – Use Hypotheses + Gate foundation to ship Debate v0.

---

## 📚 Common References

- **Cognitive Scholar Brainstorm**: `docs/tasks/theoria_feature_brainstorm_cognitive_scholar_v_1.md`
- **Reasoning Architecture**: `docs/AGENT_THINKING_ENHANCEMENT.md`
- **API Patterns**: `docs/IMPLEMENTATION_GUIDE.md`
- **UI Standards**: `docs/ui_guidelines.md`

---

## ✅ Task Completion Checklist

When completing a Cognitive Scholar task:

- [ ] Acceptance criteria satisfied and demo recorded (if applicable)
- [ ] Tests written/passing across Python + TypeScript layers
- [ ] Telemetry/metrics updated with new fields
- [ ] Documentation updated (roadmap + relevant READMEs)
- [ ] Follow-up tasks captured for Alpha/Beta scope

---

**Note**: Discovery engine tasks have been archived under `docs/archive/planning/discovery-tasks/` for historical reference.
