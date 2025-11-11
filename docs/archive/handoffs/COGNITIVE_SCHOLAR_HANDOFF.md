# Cognitive Scholar Implementation - Handoff Document

**Date**: 2025-10-18  
**Status**: Foundation Complete → Ready for MVP Implementation  
**Next Action**: Start CS-001 (Reasoning Timeline UI)

---

## 🎯 Mission

Transform Theoria into an autonomous, context-aware "super-scholar" that forms, tests, and refines theories with transparent reasoning while remaining user-steerable.

**Master Spec**: `docs/tasks/theoria_feature_brainstorm_cognitive_scholar_v_1.md` (332 lines)

---

## ✅ What's Complete

### Architecture Foundation
- **Hexagonal architecture** implemented (DTOs, repositories, mappers, domain errors)
- **Repository pattern** working: `DocumentRepository`, `DiscoveryRepository`, `IngestionJobRepository`
- **Error handling** with `ValidationError` → HTTP 422 mapping
- **Query optimizations** tools available (eager loading, monitoring decorators)
- **Architecture tests** enforcing layer boundaries

### Domain Components
- **Gap Detection Engine** exists: `theo/domain/discoveries/gap_engine.py` ✅
  - Uses BERTopic for topic modeling
  - Compares corpus vs `data/seeds/theological_topics.yaml`
  - Returns `GapDiscovery` objects with search-ready metadata
  - **Status**: Implemented but not yet wired into discovery service

- **Discovery Feed UI** complete ✅
  - 6 discovery types: pattern, contradiction, gap, connection, trend, anomaly
  - Frontend components: `DiscoveryCard`, `DiscoveryFilter`
  - Beautiful responsive design with dark mode
  - **Status**: Needs backend FastAPI endpoints

### Recent Changes
- Created `theo/infrastructure/api/app/models/reasoning.py` with Timeline data structures
- Archived TASK_001 (repository migration) as completed
- Created TASK_005 with 16 Cognitive Scholar MVP tickets (CS-001 to CS-016)
- Updated tasks README with phased execution order

---

## 📋 Immediate Next Steps (Priority Order)

### Foundation Wrap-Up (~4-6 hours)

**Optional but recommended before starting MVP**:

1. **TASK_004: Validate Architecture** (30min)
   ```bash
   pytest tests/architecture/ -v
   pytest tests/application/repositories/ -v
   ```

2. **TASK_003: Add Query Optimizations** (1-2hrs)
   - Add eager loading to search endpoint
   - Add monitoring decorators
   - Prepares for Retrieval Budgeter (CS-015)
   - File: `theo/infrastructure/api/app/routes/search.py`

3. **TASK_002: Wire Gap Engine** (3-4hrs)
   - Integrate `GapDiscoveryEngine` into `DiscoveryService.refresh()`
   - Test with `theological_topics.yaml`
   - Verify gaps appear in Discovery Feed
   - File: `theo/infrastructure/api/app/discoveries/service.py`

**Decision**: Can skip these and go straight to MVP if you want. They're nice-to-haves, not blockers.

---

## 🚀 Cognitive Scholar MVP (Main Work - 2-4 weeks)

### Week 1: Control Surface + Timeline (CS-001 to CS-004)

**CS-001: Reasoning Timeline UI** (6-8 hours) ✅ **COMPLETE**
- **Backend**: `theo/infrastructure/api/app/models/reasoning.py` ✅ CREATED
- **Frontend**: `theo/services/web/app/components/ReasoningTimeline.tsx` ✅ CREATED
- **API**: `theo/infrastructure/api/app/routes/ai/workflows/chat.py` ✅ MODIFIED
- **Goal**: Show 7 workflow steps (Understand → Gather → Tensions → Draft → Critique → Revise → Synthesize)
- **Acceptance**: ✅ Timeline appears in chat response, steps are collapsible, shows citations
- **See**: `CS-001_COMPLETE.md` for implementation details

**CS-002: Stop/Step/Pause Controls** (4 hours)
- Add loop control API endpoints
- Frontend control buttons
- Enables user steerability

**CS-003: Live Plan Panel** (6 hours)
- Shows queued queries/tools
- Drag-and-drop reordering
- Inline query editing

**CS-004: Argument Link Schema** (4 hours)
- Domain models for Toulmin structure
- Repository interface

### Week 2: Argument Maps + TMS (CS-005 to CS-008)

**CS-005: Argument Map Renderer** (8 hours)
- D3.js graph visualization
- Nodes = claims, edges = support/contradict
- Click → Toulmin zoom

**CS-006: Toulmin Zoom Modal** (4 hours)
- Detail view: claim/grounds/warrant/backing/qualifier/rebuttals

**CS-007: TMS Core** (8-10 hours)
- Truth-maintenance with justification links
- Cascade retraction on contradiction
- Unit tests

**CS-008: TMS Explorer UI** (6 hours)
- Dependency tree visualization
- Impact preview

### Week 3: Hypotheses + Debates (CS-009 to CS-013)

**CS-009: Hypothesis Object + Dashboard** (6 hours)
- Domain model + repository
- Hypothesis card UI

**CS-010: Multi-Hypothesis Runner** (8 hours)
- Generate 2-4 hypotheses per question
- Parallel retrieval/scoring

**CS-011: Debate v0** (10 hours)
- Internal debate: H1 vs H2
- One rebuttal round
- LLM judge adjusts confidence

**CS-012: Belief Bars** (4 hours)
- Prior→posterior visualization
- Per-evidence deltas

**CS-013: Meta-Prompt Picker** (6 hours)
- User selects research procedures
- Registry: `data/meta_prompts/procedures.yaml`

### Week 4: Gap→Loop Integration (CS-014 to CS-016)

**CS-014: Falsifier Search Operator** (6 hours)
- Convert gaps → exception/anomaly queries

**CS-015: Retrieval Budgeter** (8 hours)
- Execute within cost/time/token limits

**CS-016: Gap→Loop Wiring** (6 hours)
- Connect gap detection → falsifier searches → belief updates

---

## 📁 Key Files Reference

### Existing (Ready to Use)
```
theo/domain/discoveries/gap_engine.py          # Gap detection ✅
theo/adapters/persistence/document_repository.py    # Document queries ✅
theo/adapters/persistence/discovery_repository.py   # Discovery storage ✅
theo/adapters/persistence/mappers.py                # ORM ↔ DTO conversion ✅
theo/services/web/app/discoveries/              # Discovery Feed UI ✅
data/seeds/theological_topics.yaml             # Reference taxonomy ✅
```

### New (To Create for MVP)
```
# Week 1 - Timeline
theo/infrastructure/api/app/models/reasoning.py      # Timeline models ✅ CREATED
theo/services/web/app/components/ReasoningTimeline.tsx
theo/services/web/app/components/LoopControls.tsx
theo/services/web/app/components/PlanPanel.tsx

# Week 2 - Arguments + TMS
theo/domain/arguments/models.py                # Toulmin structure
theo/domain/arguments/tms.py                   # Truth-maintenance logic
theo/services/web/app/components/ArgumentMap.tsx
theo/services/web/app/components/ToulminZoom.tsx

# Week 3 - Hypotheses
theo/domain/hypotheses/models.py               # Hypothesis domain objects
theo/adapters/persistence/hypothesis_repository.py
theo/infrastructure/api/app/ai/debate.py
theo/services/web/app/components/HypothesisCard.tsx

# Week 4 - Research Loop
theo/infrastructure/api/app/research/falsifier_operator.py
theo/infrastructure/api/app/research/retrieval_budgeter.py
theo/infrastructure/api/app/ai/research_loop.py      # Orchestrator
```

---

## 🔗 Integration Points

### Gap Engine → Falsifier Searches
```python
# Existing: GapDiscovery has search-ready metadata
gap = GapDiscovery(
    reference_topic="Soteriology",
    missing_keywords=["salvation", "justification"],
    confidence=0.78,
    metadata={"search_hints": ["soteriology exceptions"]}
)

# New CS-014: Convert to queries
operator = FalsifierSearchOperator()
queries = operator.generate_queries([gap])
# Returns: ["alternative theological perspectives on salvation"]
```

### Repository Pattern → New Features
```python
# Existing repositories work the same way
class SQLAlchemyHypothesisRepository(HypothesisRepository):
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, hypothesis: Hypothesis) -> HypothesisDTO:
        # Follow existing pattern from DiscoveryRepository
        model = HypothesisModel(**hypothesis.to_dict())
        self.session.add(model)
        self.session.flush()
        return hypothesis_to_dto(model)
```

---

## 🎯 Critical Path

**Must complete in order**:
1. CS-001 (Timeline) → Enables visibility into reasoning
2. CS-002 (Controls) → Enables user steerability
3. CS-003 (Plan) → Enables loop manipulation
4. Rest can be done in parallel after foundation

**Timeline blocks everything else** - start there.

---

## 📚 Documentation Reference

- **Master Spec**: `docs/tasks/theoria_feature_brainstorm_cognitive_scholar_v_1.md`
- **Execution Plan**: `docs/tasks/TASK_005_Cognitive_Scholar_MVP_Tickets.md`
- **Integration Map**: `docs/tasks/COGNITIVE_SCHOLAR_INTEGRATION_MAP.md`
- **Architecture Guide**: `docs/ARCHITECTURE_IMPROVEMENTS.md`
- **Tasks README**: `docs/tasks/README.md`

---

## 🚨 What NOT to Do

❌ Skip CS-001 (Timeline) - it's the foundation  
❌ Try to implement all 16 tickets at once  
❌ Optimize before it works  
❌ Write perfect prompts before structure exists  
❌ Add features not in the spec (stay focused)

---

## ✅ Quick Start: CS-001 Implementation

### 1. Backend Models (DONE ✅)
File: `theo/infrastructure/api/app/models/reasoning.py` created with:
- `ReasoningStepType` enum
- `ReasoningStep` model
- `ReasoningTimeline` model

### 2. Frontend Component (NEXT)
Create: `theo/services/web/app/components/ReasoningTimeline.tsx`

**Minimal structure**:
```tsx
export function ReasoningTimeline({ timeline }: { timeline: ReasoningTimeline }) {
  return (
    <div className="reasoning-timeline">
      {timeline.steps.map((step, index) => (
        <TimelineStep key={step.id} step={step} isActive={index === timeline.current_step_index} />
      ))}
    </div>
  );
}
```

### 3. Wire into Chat (AFTER UI WORKS)
Modify: `theo/infrastructure/api/app/routes/ai/workflows/chat.py`

Return timeline alongside answer:
```python
return {
    "answer": answer,
    "timeline": timeline.model_dump(),
}
```

### 4. Test with Mock Data
```python
timeline = ReasoningTimeline(
    session_id="test",
    question="What is justification?",
    steps=[
        ReasoningStep(id="1", step_type="understand", title="Understanding question", status="completed"),
        ReasoningStep(id="2", step_type="gather", title="Gathering evidence", status="in_progress"),
        # ... 5 more steps
    ],
    created_at=datetime.now(UTC),
    updated_at=datetime.now(UTC),
)
```

---

## 🎯 Success Criteria for CS-001

- [ ] Timeline component renders in chat UI
- [ ] 7 steps shown with correct status icons
- [ ] Steps are collapsible/expandable
- [ ] Duration displayed for completed steps
- [ ] Citations list visible when expanded
- [ ] Dark mode support
- [ ] Works with mock data

**Time budget**: 6-8 hours  
**Blocks**: CS-002, CS-003 (controls need timeline to operate on)

---

## 💾 State Management Notes

For MVP, store timeline in:
- **Option 1**: Chat session metadata (simplest)
- **Option 2**: Separate `reasoning_timelines` table (cleaner)
- **Option 3**: Redis cache (faster, but ephemeral)

**Recommendation**: Start with Option 1 (session metadata), migrate to Option 2 later.

---

## 🔧 Development Tips

1. **Build incrementally**: Get Timeline showing static data first, then make it dynamic
2. **Use existing chat as entry point**: Don't create new routes yet
3. **Mock aggressively**: Fake the 7 steps initially, wire real logic later
4. **Test in isolation**: Build Timeline component in Storybook if available
5. **Reference Discovery UI**: Similar collapsible card pattern exists there

---

## 📊 Progress Tracking

Update `docs/tasks/TASK_005_Cognitive_Scholar_MVP_Tickets.md` as you complete tickets.

Mark checkboxes:
- [x] CS-001 ✅ **COMPLETE** (2025-10-18)
- [x] CS-002 ✅ COMPLETE (2025-10-18) ← **NEXT**
- [ ] CS-003
- ...

---

## 🆘 If You Get Stuck

**Timeline not rendering?**
- Check: Is `timeline` prop reaching component?
- Check: Are step types valid enum values?
- Check: CSS module imported correctly?

**Backend returns 500?**
- Check: All imports present in `reasoning.py`?
- Check: Pydantic models serialize correctly?
- Check: `model_dump()` vs `dict()` (use `model_dump()`)

**Need more detail on a ticket?**
- See: `docs/tasks/TASK_005_Cognitive_Scholar_MVP_Tickets.md`
- See: `docs/tasks/COGNITIVE_SCHOLAR_INTEGRATION_MAP.md`

---

## 🎯 Your Action Plan (Next 48 Hours)

**Today**:
1. ✅ Confirm CS-001 handoff context
2. ✅ Ship loop control endpoints + UI (CS-002)
3. ✅ Capture partial-response tests for stop/pause

**Tomorrow**:
1. Kick off CS-003 (Plan Panel design & state wiring)
2. Define research plan DTOs on the backend
3. Outline integration coverage for plan edits

**Day 3**:
1. Implement PlanPanel.tsx with live updates
2. Connect plan DTOs to chat workflow
3. Backfill UI tests after layout stabilises

**Goal**: Loop controls live, Plan Panel scaffolding underway.

---

**Ready to code CS-001? Start with the frontend component!** 🚀
