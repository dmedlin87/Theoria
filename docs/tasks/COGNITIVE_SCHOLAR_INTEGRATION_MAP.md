# Cognitive Scholar Integration Map

**Purpose**: Visual guide showing how existing components (gap engine, repositories, discovery feed) integrate with new Cognitive Scholar features.

**Last updated**: 2025-10-18

---

## 🗺️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER INTERFACE LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  Reasoning   │  │  Hypothesis  │  │  Argument    │        │
│  │  Timeline    │  │  Dashboard   │  │  Map         │        │
│  │  (CS-001)    │  │  (CS-009)    │  │  (CS-005)    │        │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘        │
│         │                  │                  │                 │
│         └──────────────────┼──────────────────┘                 │
│                            │                                    │
├────────────────────────────┼────────────────────────────────────┤
│                  ORCHESTRATION LAYER                            │
├────────────────────────────┼────────────────────────────────────┤
│                            │                                    │
│                 ┌──────────▼──────────┐                        │
│                 │  Research Loop      │                        │
│                 │  Orchestrator       │                        │
│                 │  (CS-002, CS-016)   │                        │
│                 └──────────┬──────────┘                        │
│                            │                                    │
│         ┌──────────────────┼──────────────────┐                │
│         │                  │                  │                │
│   ┌─────▼─────┐     ┌─────▼──────┐    ┌─────▼──────┐         │
│   │ Detective │     │   Critic   │    │   Debate   │         │
│   │  Prompt   │     │   Prompt   │    │Orchestrator│         │
│   │           │     │            │    │  (CS-011)  │         │
│   └───────────┘     └────────────┘    └────────────┘         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                     COGNITIVE SERVICES                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ Gap Detection   │  │  Falsifier       │  │  Hypothesis   │ │
│  │ Engine ✅       │  │  Search Operator │  │  Generator    │ │
│  │ (EXISTING)      │  │  (CS-014)        │  │  (CS-010)     │ │
│  └────────┬────────┘  └────────┬─────────┘  └───────┬───────┘ │
│           │                    │                     │         │
│           │    ┌───────────────▼──────┐             │         │
│           │    │  Retrieval Budgeter  │             │         │
│           │    │  (CS-015)            │             │         │
│           │    └───────────┬──────────┘             │         │
│           │                │                        │         │
│           └────────────────┼────────────────────────┘         │
│                            │                                   │
├────────────────────────────┼───────────────────────────────────┤
│                    DOMAIN LAYER                                │
├────────────────────────────┼───────────────────────────────────┤
│                            │                                   │
│  ┌─────────────────────────▼────────────────────────┐         │
│  │           Truth-Maintenance System (TMS)         │         │
│  │           (CS-007, CS-008)                       │         │
│  │                                                   │         │
│  │  • Justification links                           │         │
│  │  • Cascade retractions                           │         │
│  │  • Dependency preview                            │         │
│  └──────────────────────┬────────────────────────────┘         │
│                         │                                      │
│         ┌───────────────┼────────────────┐                    │
│         │               │                │                    │
│   ┌─────▼──────┐  ┌────▼─────┐   ┌─────▼─────┐              │
│   │ Hypothesis │  │ Argument │   │ Evidence  │              │
│   │   Model    │  │   Link   │   │   Object  │              │
│   │  (CS-009)  │  │ (CS-004) │   │           │              │
│   └────────────┘  └──────────┘   └───────────┘              │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                  PERSISTENCE LAYER ✅                         │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  Document      │  │  Discovery   │  │  Hypothesis     │  │
│  │  Repository    │  │  Repository  │  │  Repository     │  │
│  │  ✅ READY     │  │  ✅ READY    │  │  (new CS-009)   │  │
│  └────────────────┘  └──────────────┘  └─────────────────┘  │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow: Gap Detection → Falsifier Search → Belief Update

### Phase 1: Gap Detection (EXISTING - TASK_002)

```
1. User uploads documents
2. Discovery refresh triggered
3. Gap Engine analyzes corpus:
   ┌─────────────────────────────────────────┐
   │ GapDiscoveryEngine.detect()            │
   │                                         │
   │ • Load documents via DocumentRepository │
   │ • Extract embeddings from DTOs          │
   │ • BERTopic.fit_transform()             │
   │ • Compare vs theological_topics.yaml    │
   │ • Return GapDiscovery objects          │
   └─────────────────────────────────────────┘
   
4. Gap persisted to discoveries table
5. Frontend displays gap in Discovery Feed ✅
```

**Output**: `GapDiscovery` objects with metadata:
```json
{
  "discovery_type": "gap",
  "title": "Under-represented: Soteriology",
  "reference_topic": "Soteriology",
  "missing_keywords": ["salvation", "justification", "sanctification"],
  "confidence": 0.78,
  "metadata": {
    "priority": 0.85,
    "search_hints": ["soteriology exceptions", "alternative salvation views"]
  }
}
```

---

### Phase 2: Falsifier Search (NEW - CS-014, CS-015)

```
1. Research loop receives GapDiscovery signals
2. Falsifier Operator generates queries:
   ┌─────────────────────────────────────────┐
   │ FalsifierSearchOperator.generate()     │
   │                                         │
   │ • Input: GapDiscovery objects           │
   │ • Templates: "exceptions to X"          │
   │              "contradictions about Y"   │
   │              "alternative views on Z"   │
   │ • Output: Search queries + filters      │
   └─────────────────────────────────────────┘
   
3. Retrieval Budgeter executes queries:
   ┌─────────────────────────────────────────┐
   │ RetrievalBudgeter.execute()            │
   │                                         │
   │ • Budget: max_docs=50, max_tokens=10k  │
   │ • Execute queries sequentially          │
   │ • Summarize if token limit hit          │
   │ • Return: results + budget_status       │
   └─────────────────────────────────────────┘
   
4. Results feed back into hypothesis updater
```

**Example Query Generated**:
```json
{
  "query_text": "alternative theological perspectives on salvation and justification",
  "filters": {
    "expected_stance": "contradictory",
    "exclude_sources": ["already_read_doc_ids"]
  },
  "priority": 0.85,
  "budget_allocation": {
    "max_docs": 10,
    "max_tokens": 2000
  }
}
```

---

### Phase 3: Belief Update & TMS (NEW - CS-007, CS-012)

```
1. Falsifier evidence retrieved
2. Hypothesis Updater revises beliefs:
   ┌─────────────────────────────────────────┐
   │ HypothesisUpdater.revise_beliefs()     │
   │                                         │
   │ • Compare evidence vs hypothesis        │
   │ • Bayesian update: prior → posterior    │
   │ • If contradictory: lower confidence    │
   │ • If supportive: raise confidence       │
   │ • Record justification links (TMS)      │
   └─────────────────────────────────────────┘
   
3. TMS tracks dependencies:
   ┌─────────────────────────────────────────┐
   │ TruthMaintenanceSystem                 │
   │                                         │
   │ • Hypothesis depends_on Evidence        │
   │ • Evidence supports/contradicts Claim   │
   │ • On retraction: cascade invalidation   │
   │ • Preview impact before applying        │
   └─────────────────────────────────────────┘
   
4. UI updates:
   - Belief bars show prior → posterior
   - Argument map shows new edges
   - Timeline records "Gap filled: Soteriology"
```

---

## 🔗 Integration Points: Existing ↔ New

### 1. Gap Engine → Falsifier Operator (CS-014)

**Existing Code**:
- `theo/domain/discoveries/gap_engine.py` ✅
- Returns `GapDiscovery` objects ✅

**New Integration** (CS-014):
```python
# theo/services/api/app/research/falsifier_operator.py
class FalsifierSearchOperator:
    def generate_queries(
        self, 
        gap_signals: list[GapDiscovery]
    ) -> list[SearchQuery]:
        queries = []
        for gap in gap_signals:
            # Use gap.missing_keywords and gap.reference_topic
            query = self._build_falsifier_query(
                topic=gap.reference_topic,
                keywords=gap.missing_keywords,
                priority=gap.confidence
            )
            queries.append(query)
        return queries
```

**Action**: Wire gap engine output into falsifier operator input.

---

### 2. Discovery Repository → Hypothesis Repository (CS-009)

**Existing Code**:
- `theo/adapters/persistence/discovery_repository.py` ✅
- Stores discoveries with metadata ✅

**New Pattern** (CS-009):
```python
# theo/adapters/persistence/hypothesis_repository.py
class SQLAlchemyHypothesisRepository(HypothesisRepository):
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, hypothesis: Hypothesis) -> Hypothesis:
        # Similar pattern to discovery repository
        model = HypothesisModel(**hypothesis.to_dict())
        self.session.add(model)
        self.session.flush()
        return hypothesis_to_dto(model)
```

**Action**: Follow existing repository pattern; add Hypothesis table to schema.

---

### 3. DocumentRepository → Research Loop (CS-016)

**Existing Code**:
- `theo/adapters/persistence/document_repository.py` ✅
- `list_with_embeddings()` method ✅
- `list_created_since()` method ✅

**Usage in Research Loop** (CS-016):
```python
# theo/services/api/app/ai/research_loop.py
class ResearchLoopOrchestrator:
    def __init__(
        self,
        document_repo: DocumentRepository,
        gap_engine: GapDiscoveryEngine,
        falsifier_operator: FalsifierSearchOperator,
        # ...
    ):
        self.document_repo = document_repo
        self.gap_engine = gap_engine
        self.falsifier_operator = falsifier_operator
    
    def execute(self, user_id: str) -> ResearchLoopResult:
        # 1. Get documents via repository
        documents = self.document_repo.list_with_embeddings(user_id)
        
        # 2. Run gap detection
        gaps = self.gap_engine.detect(documents)
        
        # 3. Generate falsifier queries
        queries = self.falsifier_operator.generate_queries(gaps)
        
        # 4. Execute retrieval...
```

**Action**: Inject existing repositories into new orchestrator.

---

## ✅ Readiness Checklist

### Already Complete
- ✅ Repository pattern implemented (TASK_001)
- ✅ Gap engine exists (`theo/domain/discoveries/gap_engine.py`)
- ✅ DocumentRepository with `list_with_embeddings()`
- ✅ DiscoveryRepository for persisting findings
- ✅ Discovery Feed UI (frontend complete)
- ✅ Architecture tests enforcing boundaries

### Ready to Implement (Foundation)
- ⏳ TASK_002: Integrate gap engine into discovery refresh
- ⏳ TASK_003: Query optimizations for retrieval budgeter
- ⏳ TASK_004: Validate architecture foundation

### Ready to Implement (Cognitive Scholar MVP)
- 🔲 CS-001 to CS-016: See TASK_005 for detailed breakdown
- 🔲 Each ticket builds on existing patterns (DTOs, repositories, domain objects)
- 🔲 Critical path: Timeline → Controls → Argument Maps → TMS → Hypotheses → Gap Loop

---

## 🎯 Next Steps

### This Week (Foundation)
1. **Run TASK_004** (30min) - Validate current architecture
2. **Complete TASK_003** (1-2hrs) - Add query optimizations
3. **Finalize TASK_002** (3-4hrs) - Wire gap engine into discovery service

### Next Week (Start MVP)
4. **CS-001** (6-8hrs) - Build Reasoning Timeline UI
5. **CS-002** (4hrs) - Add Stop/Step/Pause controls
6. **CS-003** (6hrs) - Implement Live Plan Panel
7. **CS-004** (4hrs) - Define Argument Link schema

**Target**: Have Timeline + Controls working by end of Week 1, enabling full steerability.

---

## 📚 References

- **Gap Engine**: `theo/domain/discoveries/gap_engine.py` (existing)
- **Repository Pattern**: `theo/application/repositories/*.py` (existing)
- **Cognitive Scholar Spec**: `docs/tasks/theoria_feature_brainstorm_cognitive_scholar_v_1.md`
- **MVP Tickets**: `docs/tasks/TASK_005_Cognitive_Scholar_MVP_Tickets.md`
- **Architecture Guide**: `docs/architecture/improvements.md`
