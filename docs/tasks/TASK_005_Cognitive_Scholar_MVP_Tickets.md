# TASK 005: Cognitive Scholar MVP Implementation Tickets

**Priority**: ⭐⭐⭐ HIGH  
**Timeline**: 2-4 weeks (MVP phase)  
**Dependencies**: Architecture foundation (✅), Gap engine (exists), TASK_002-004  
**Status**: Phase 1 control-surface features landed (CS-001 → CS-003); streaming plan telemetry pending follow-up
**Reference**: `theoria_feature_brainstorm_cognitive_scholar_v_1.md` Appendix §A

---

## 🎯 Objective

Break down the Cognitive Scholar MVP into discrete, implementable tickets following the execution order defined in the spec.

---

## 📋 MVP Ticket Breakdown

### Phase 1: Control Surface + Timeline (Week 1)

#### Ticket CS-001: Reasoning Timeline UI Component ✅ COMPLETE
**Estimate**: 6-8 hours (Actual: ~4 hours)
**Dependencies**: None  
**Description**: Implement collapsible Reasoning Timeline showing workflow steps (Understand → Gather → Tensions → Draft → Critique → Revise → Synthesize).

**Acceptance Criteria**:
- [x] React component renders 7 workflow steps
- [x] Each step shows: status icon, title, duration, citations used
- [x] Steps are collapsible/expandable
- [x] Jump-to-edit action per step
- [x] Dark mode support
- [x] Integrates with existing chat interface

**Files**:
- `theo/services/web/app/components/ReasoningTimeline.tsx` ✅ CREATED
- `theo/services/web/app/components/ReasoningTimeline.module.css` ✅ CREATED  
- `theo/services/api/app/routes/ai/workflows/chat.py` ✅ MODIFIED
- `theo/services/api/app/models/ai.py` ✅ MODIFIED

**Completed**: 2025-10-18  
**See**: `CS-001_COMPLETE.md` for details

---

#### Ticket CS-002: Stop/Step/Pause Controls ✅ COMPLETE
**Estimate**: 4 hours  
**Dependencies**: CS-001  
**Description**: Add interactive controls allowing users to pause research loops, step through one tool call at a time, or stop mid-workflow.

**Acceptance Criteria**:
- [x] Stop button halts current loop, returns partial synthesis
- [x] Step button advances one tool call, shows next queued action
- [x] Pause button holds loop, preserves state
- [x] UI shows current loop status (running/paused/stopped)
- [x] Backend API supports loop control (`POST /api/chat/loop/control`)

**Files**:
- `theo/services/web/app/components/LoopControls.tsx` ✅ CREATED
- `theo/services/api/app/routes/ai/workflows/chat.py` ✅ MODIFIED
- `theo/services/api/app/ai/research_loop.py` ✅ CREATED

**Completed**: 2025-10-18  
**Notes**: Loop controls orchestrate stop, pause/resume, and step actions with persisted state and partial response handling.

---

#### Ticket CS-003: Live Plan Panel ✅ COMPLETE
**Estimate**: 6 hours  
**Dependencies**: CS-002  
**Description**: Display miniature plan showing queued queries, tools to call, and step priorities. Allow inline editing and reprioritization.

**Acceptance Criteria**:
- [x] Panel lists current loop plan: steps, queries, tools
- [x] Each item shows: order, status, estimated cost/time
- [x] Drag-and-drop to reorder steps
- [x] Inline edit query text
- [x] Skip action per step
- [ ] Real-time updates as loop executes *(streaming deltas follow-up; snapshot refresh shipping today)*

**Files**:
- `theo/services/api/app/models/research_plan.py` ✅ CREATED
- `theo/services/api/app/ai/research_loop.py` ✅ MODIFIED
- `theo/services/api/app/routes/ai/workflows/chat.py` ✅ MODIFIED
- `theo/services/web/app/components/PlanPanel.tsx` ✅ CREATED
- `theo/services/web/app/components/PlanPanel.module.css` ✅ CREATED
- `theo/services/web/app/chat/ChatWorkspace.tsx` ✅ MODIFIED
- `theo/services/web/app/lib/api-client.ts` ✅ MODIFIED
- `theo/services/web/app/lib/api-normalizers.ts` ✅ MODIFIED
- `theo/services/web/app/lib/chat-client.ts` ✅ MODIFIED
- `theo/services/web/tests/app/chat/chat-workspace.test.tsx` ✅ MODIFIED
- `tests/api/test_chat_loop_controls.py` ✅ MODIFIED

---

### Phase 2: Argument Mapping + Toulmin Zoom (Week 1-2)

#### Ticket CS-004: Argument Link Schema (Backend)
**Estimate**: 4 hours  
**Dependencies**: None  
**Description**: Implement data models for Toulmin argument structure (claim/grounds/warrant/backing/qualifier/rebuttal).

**Acceptance Criteria**:
- [ ] `ArgumentLink` model with Toulmin fields
- [ ] `Claim`, `Evidence`, `Warrant` domain objects
- [ ] JSON schema for argument graphs
- [ ] Repository interface for argument persistence
- [ ] SQLAlchemy adapter implementation

**Files**:
- `theo/domain/arguments/__init__.py` (new)
- `theo/domain/arguments/models.py` (new)
- `theo/adapters/persistence/argument_repository.py` (new)
- `theo/adapters/persistence/models.py` (modify - add ArgumentLink table)

---

#### Ticket CS-005: Argument Map Renderer
**Estimate**: 8 hours  
**Dependencies**: CS-004  
**Description**: Frontend component rendering argument graphs with nodes (claims) and edges (support/contradict).

**Acceptance Criteria**:
- [ ] D3.js or similar graph visualization
- [ ] Nodes show claim text + confidence bar
- [ ] Edges labeled with relation type (supports/contradicts/depends_on)
- [ ] Click claim → Toulmin zoom (see CS-006)
- [ ] Hover ground → shows source span + credibility badge
- [ ] Export to PNG/PDF

**Files**:
- `theo/services/web/app/components/ArgumentMap.tsx` (new)
- `theo/services/web/app/components/argument-map.module.css` (new)
- `theo/services/api/app/routes/arguments.py` (new - argument graph endpoints)

---

#### Ticket CS-006: Toulmin Zoom Modal
**Estimate**: 4 hours  
**Dependencies**: CS-005  
**Description**: Detailed view showing Toulmin structure for a selected claim.

**Acceptance Criteria**:
- [ ] Modal triggered from argument map click
- [ ] Displays: claim, grounds (evidence list), warrant, backing, qualifier, rebuttals
- [ ] Each ground shows: quote, source, credibility badge
- [ ] Click source → opens document viewer
- [ ] Edit mode for advanced users (future hook)

**Files**:
- `theo/services/web/app/components/ToulminZoom.tsx` (new)

---

### Phase 3: TMS v0 + Auto-Retractions (Week 2)

#### Ticket CS-007: Truth-Maintenance System (TMS) Core
**Estimate**: 8-10 hours  
**Dependencies**: CS-004  
**Description**: Implement minimal TMS with justification links and cascade retraction on contradiction.

**Acceptance Criteria**:
- [ ] `Justification` model linking conclusions to premises
- [ ] `depends_on` edges in argument graph
- [ ] Retract operation: mark node invalid, cascade to dependents
- [ ] Preview API: show impact before applying retract
- [ ] Event log records retraction cascade
- [ ] Unit tests for multi-level cascades

**Files**:
- `theo/domain/arguments/tms.py` (new - TMS logic)
- `theo/adapters/persistence/models.py` (modify - add Justification table)
- `theo/services/api/app/routes/arguments.py` (modify - add retract endpoint)
- `tests/domain/arguments/test_tms.py` (new)

---

#### Ticket CS-008: TMS Dependency Explorer UI
**Estimate**: 6 hours  
**Dependencies**: CS-007  
**Description**: Visualize which claims/evidence will retract if a premise changes.

**Acceptance Criteria**:
- [ ] UI component showing dependency tree
- [ ] Highlight impacted nodes in red
- [ ] Count: "Retracting this will invalidate N claims"
- [ ] Confirm/Cancel retraction dialog
- [ ] Real-time graph update on retraction

**Files**:
- `theo/services/web/app/components/TMSExplorer.tsx` (new)

---

### Phase 4: Two-Track Hypotheses + Debate v0 (Week 2-3)

#### Ticket CS-009: Hypothesis Object + Dashboard
**Estimate**: 6 hours  
**Dependencies**: None  
**Description**: Implement Hypothesis domain model and dashboard UI.

**Acceptance Criteria**:
- [ ] `Hypothesis` model: id, question_id, thesis, priors, confidence, status, supporting_evidence[], counter_evidence[], assumptions[], notes
- [ ] Repository interface + SQLAlchemy adapter
- [ ] Hypothesis card UI: thesis, confidence bar, supports/contradictions, open questions
- [ ] List view showing multiple hypotheses per question
- [ ] CRUD API endpoints

**Files**:
- `theo/domain/hypotheses/__init__.py` (new)
- `theo/domain/hypotheses/models.py` (new)
- `theo/adapters/persistence/hypothesis_repository.py` (new)
- `theo/services/web/app/components/HypothesisCard.tsx` (new)
- `theo/services/api/app/routes/hypotheses.py` (new)

---

#### Ticket CS-010: Multi-Hypothesis Parallel Runner
**Estimate**: 8 hours  
**Dependencies**: CS-009  
**Description**: Generate 2-4 hypotheses, run retrieval/scoring in parallel, rank outcomes.

**Acceptance Criteria**:
- [ ] Detective prompt generates N hypotheses for a question
- [ ] Parallel retrieval per hypothesis (async/threads)
- [ ] Scoring: evidence count, confidence, diversity
- [ ] Ranked hypothesis list returned to frontend
- [ ] User can select preferred hypothesis or merge

**Files**:
- `theo/services/api/app/ai/hypothesis_generator.py` (new)
- `theo/services/api/app/ai/hypothesis_scorer.py` (new)
- `theo/services/api/app/routes/ai/workflows/multi_hypothesis.py` (new)

---

#### Ticket CS-011: Debate v0 (Single Round)
**Estimate**: 10 hours  
**Dependencies**: CS-010  
**Description**: Internal debate between H1 vs H2, one rebuttal round, simple LLM judge.

**Acceptance Criteria**:
- [ ] Debate orchestrator: assigns roles (Pro H1, Pro H2)
- [ ] One opening statement per side
- [ ] One rebuttal per side
- [ ] Judge LLM evaluates arguments, picks winner, provides rationale
- [ ] Verdict adjusts hypothesis confidence (winner +0.1, loser -0.1 or configurable)
- [ ] Debate transcript stored + retrievable
- [ ] API endpoint: `POST /api/debates/run`

**Files**:
- `theo/services/api/app/ai/debate.py` (new)
- `theo/services/api/app/models/debate.py` (new - debate DTOs)
- `theo/adapters/persistence/models.py` (modify - add Debate table)
- `theo/services/api/app/routes/debates.py` (new)

---

### Phase 5: Belief Bars + Meta-Prompt Picker (Week 3)

#### Ticket CS-012: Bayesian Belief Update Visualization
**Estimate**: 4 hours  
**Dependencies**: CS-009  
**Description**: Show prior→posterior bars per hypothesis after each evidence batch.

**Acceptance Criteria**:
- [ ] Belief bar chart: prior (light), posterior (dark)
- [ ] Per-evidence delta annotations
- [ ] Tooltip shows: evidence ID, impact (+0.05), reason
- [ ] Calibration metric logged (Brier score)
- [ ] Updates in real-time during loop

**Files**:
- `theo/services/web/app/components/BeliefBars.tsx` (new)
- `theo/services/api/app/ai/belief_updater.py` (new - Bayesian logic)

---

#### Ticket CS-013: Meta-Prompt Library + Picker UI
**Estimate**: 6 hours  
**Dependencies**: None  
**Description**: User selects research procedures (Scientific Method, Historical-Critical, Debate-First, etc.).

**Acceptance Criteria**:
- [ ] Meta-prompt registry: YAML/JSON with procedure definitions
- [ ] Each procedure: name, description, steps, parameters
- [ ] UI dropdown or modal for selection
- [ ] Selected procedure passed to orchestrator
- [ ] API returns procedure metadata: `GET /api/meta-prompts`

**Files**:
- `data/meta_prompts/procedures.yaml` (new - prompt library)
- `theo/services/api/app/meta_prompts.py` (new - registry loader)
- `theo/services/web/app/components/ProcedurePicker.tsx` (new)
- `theo/services/api/app/routes/meta_prompts.py` (new)

---

### Phase 6: Gap→Loop Wiring (Week 3-4)

#### Ticket CS-014: Falsifier Search Operator
**Estimate**: 6 hours  
**Dependencies**: TASK_002 (Gap engine exists)  
**Description**: Convert gap signals into anomaly/exception search queries.

**Acceptance Criteria**:
- [ ] Input: GapDiscovery objects from gap engine
- [ ] Output: List of search queries (text + filters)
- [ ] Query templates: "exceptions to X", "contradictions about Y", "alternative views on Z"
- [ ] Metadata: expected_stance (contradictory), priority
- [ ] API endpoint: `POST /api/research/falsifiers`

**Files**:
- `theo/services/api/app/research/falsifier_operator.py` (new)
- `theo/services/api/app/models/research.py` (new - query DTOs)

---

#### Ticket CS-015: Retrieval Budgeter
**Estimate**: 8 hours  
**Dependencies**: CS-014  
**Description**: Execute queries within soft caps (max docs, tokens, time).

**Acceptance Criteria**:
- [ ] Budget model: max_docs, max_tokens, max_time_seconds, max_cost_dollars
- [ ] Execute queries sequentially until budget exhausted
- [ ] Summarize/merge results if token limit hit
- [ ] Log: queries_executed, tokens_used, time_elapsed, cost
- [ ] Return: results + budget_status (under/exceeded)
- [ ] API endpoint: `POST /api/research/execute`

**Files**:
- `theo/services/api/app/research/retrieval_budgeter.py` (new)
- `theo/services/api/app/models/research.py` (modify - add Budget model)

---

#### Ticket CS-016: Gap→Loop Integration
**Estimate**: 6 hours  
**Dependencies**: CS-014, CS-015, TASK_002  
**Description**: Wire gap detection into research loop with falsifier queries.

**Acceptance Criteria**:
- [ ] After gap detection, trigger falsifier operator
- [ ] Append falsifier queries to loop plan
- [ ] Execute within retrieval budget
- [ ] Update hypotheses based on falsifier results
- [ ] UI shows "Gap detected: Soteriology → Searching for contradictory evidence..."
- [ ] Event log records gap→query→result chain

**Files**:
- `theo/services/api/app/ai/research_loop.py` (modify - add gap wiring)
- `theo/services/api/app/routes/ai/workflows/chat.py` (modify - expose gap integration)

---

## 📊 Estimated Timeline

**Week 1**: CS-001, CS-002, CS-003, CS-004  
**Week 2**: CS-005, CS-006, CS-007, CS-008  
**Week 3**: CS-009, CS-010, CS-011, CS-012  
**Week 4**: CS-013, CS-014, CS-015, CS-016

**Total**: 16 tickets, ~98-106 hours (2.5-3 weeks for single developer)

---

## ✅ MVP Success Criteria

- [ ] User can ask a question and see Reasoning Timeline with 7 steps
- [ ] Stop/Step/Pause controls work
- [ ] Argument Map renders with clickable Toulmin zoom
- [ ] TMS cascade retraction works with preview
- [ ] Multi-hypothesis runner generates 2+ hypotheses
- [ ] Debate v0 runs and adjusts confidence
- [ ] Belief bars show prior→posterior updates
- [ ] Gap detection triggers falsifier searches
- [ ] Retrieval budgeter enforces cost/time limits
- [ ] All components integrate into chat workflow

---

## 📚 References

- **Master Spec**: `theoria_feature_brainstorm_cognitive_scholar_v_1.md`
- **Execution Order**: Spec Appendix §A
- **Acceptance Checks**: Spec Appendix §B
- **Architecture Patterns**: `docs/architecture/improvements.md`

---

## 🚨 Dependencies & Risks

**Critical Path**: CS-001→CS-002→CS-003 (timeline + controls) must land first for UX  
**High-Risk**: CS-007 (TMS) is complex; start with unit tests  
**Performance**: CS-015 (budgeter) needs profiling; watch for latency spikes  
**LLM Costs**: CS-011 (debate) will consume tokens; set aggressive budgets

---

**Status**: CS-001 through CS-003 complete; next up CS-004 argument schema + plan streaming enhancements
