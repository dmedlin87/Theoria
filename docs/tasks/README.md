# Task Handoff Documents

This directory contains task specifications aligned with the **Cognitive Scholar** vision (see `theoria_feature_brainstorm_cognitive_scholar_v_1.md`). Foundation tasks provide infrastructure for autonomous research features.

---

## 🧠 Cognitive Scholar Vision

The Cognitive Scholar spec defines an autonomous, context-aware research agent with:
- Detective→Critic loops for iterative reasoning
- Hypothesis tracking and belief updates
- Truth-maintenance graphs with cascade retractions
- Knowledge-gap generators feeding falsifier searches
- Constitutional self-critique and multi-perspective debates

---

## 📋 Task List

### Completed ✅

- **[TASK_001](../archive/planning/TASK_001_Migrate_DiscoveryService_COMPLETED.md)** - Migrate DiscoveryService to New Architecture
  - ✅ Completed 2025-10-18
  - Repository pattern implemented
  - Foundation ready for Cognitive Scholar features

### Foundation Tasks (Optional - ~4-6 hours)

- **[FOUNDATION_TASKS](FOUNDATION_TASKS.md)** - Pre-MVP Foundation Work (Consolidated)
  - **F1**: Validate Architecture (30min) - Run tests, verify boundaries
  - **F2**: Add Query Optimizations (1-2hrs) - Eliminate N+1, add monitoring
  - **F3**: Wire Gap Engine (3-4hrs) - Integrate gap detection into service
  - **Status**: Optional - Can skip and go straight to CS-001
  - **Note**: TASK_002-004 consolidated here for convenience

### Cognitive Scholar MVP ⭐⭐⭐ **START HERE**

- **[TASK_005](TASK_005_Cognitive_Scholar_MVP_Tickets.md)** - Cognitive Scholar MVP Implementation  
  - **16 tickets** (CS-001 to CS-016) broken down from spec
  - Reasoning Timeline, Argument Maps, TMS, Hypotheses, Debates, Belief Bars
  - **Timeline**: 2-4 weeks (98-106 hours)
  - **Status**: ⭐ **START CS-001 (Reasoning Timeline) NOW** ⭐
  - **Backend models created**: `theo/services/api/app/models/reasoning.py` ✅

---

## 🎯 Recommended Order for Cognitive Scholar MVP

### Option A: Skip Foundation, Start MVP Immediately ⚡ (RECOMMENDED)
1. **Go straight to CS-001** (Reasoning Timeline UI)
2. Return to FOUNDATION_TASKS later if needed

### Option B: Foundation First (Optional ~4-6 hours)
1. **FOUNDATION_TASKS** (F1, F2, F3) - See `FOUNDATION_TASKS.md`
2. Then start CS-001

### Cognitive Scholar MVP (Weeks 1-4)
**START HERE** → **CS-001** (Reasoning Timeline)
   - **Week 1**: Timeline + Controls + Argument Schema (CS-001 to CS-004)
   - **Week 2**: Argument Maps + TMS (CS-005 to CS-008)
   - **Week 3**: Hypotheses + Debates (CS-009 to CS-013)
   - **Week 4**: Gap→Loop Integration (CS-014 to CS-016)

**Critical Path**: CS-001 (Timeline) → CS-002 (Controls) → CS-003 (Plan Panel) unlocks user steerability

**See**: `COGNITIVE_SCHOLAR_HANDOFF.md` for complete implementation guide

---

## 📚 Common References

### Essential Docs (Read These)
- **🚀 HANDOFF DOC**: `COGNITIVE_SCHOLAR_HANDOFF.md` (copy this to new chat session)
- **Cognitive Scholar Spec**: `theoria_feature_brainstorm_cognitive_scholar_v_1.md` (master vision)
- **MVP Tickets**: `TASK_005_Cognitive_Scholar_MVP_Tickets.md` (16 tickets, CS-001 to CS-016)
- **Integration Map**: `COGNITIVE_SCHOLAR_INTEGRATION_MAP.md` (architecture diagrams)

### Foundation Docs (Optional)
- **Foundation Tasks**: `FOUNDATION_TASKS.md` (F1-F3, optional pre-MVP work)
- **Architecture Guide**: `docs/ARCHITECTURE_IMPROVEMENTS.md`
- **Migration Guide**: `docs/ARCHITECTURE_MIGRATION_EXAMPLE.md`
- **Reference Code**: `theo/services/api/app/routes/discoveries_v1.py`

---

## ✅ Task Completion Checklist

When completing a task:

- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] Architecture tests pass
- [ ] Cognitive Scholar integration notes added (if applicable)
- [ ] Documentation updated
- [ ] Performance validated
- [ ] Lessons learned documented

---

**Note**: TASK_002-004 provide foundational infrastructure supporting the Cognitive Scholar autonomous research vision. Architecture patterns (DTOs, repositories, domain errors, API versioning) implemented October 2025.
