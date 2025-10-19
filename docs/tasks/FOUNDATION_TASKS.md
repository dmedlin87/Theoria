# Foundation Tasks - Pre-MVP Checklist

**Total Time**: ~4-6 hours  
**Status**: Optional but recommended before Cognitive Scholar MVP  
**Priority**: LOW (can skip and go straight to CS-001)

These are quick wins that strengthen the foundation before building Cognitive Scholar features.

---

## Task F1: Validate Architecture (30 minutes)

**Original**: TASK_004  
**Goal**: Verify hexagonal architecture is working correctly

### Commands
```bash
# Architecture boundary tests
pytest tests/architecture/ -v

# Repository unit tests  
pytest tests/application/repositories/ -v

# Integration tests
pytest tests/api/routes/test_discoveries_v1.py -v

# Full suite with coverage
pytest --cov=theo --cov-report=term
```

### Success Criteria
- [ ] All architecture tests pass
- [ ] No ORM imports in service layer
- [ ] DTOs immutable
- [ ] Coverage ≥ 80% for new code

---

## Task F2: Add Query Optimizations (1-2 hours)

**Original**: TASK_003  
**Goal**: Eliminate N+1 queries, add performance monitoring

### Files to Modify

**1. Search Endpoint**
```python
# theo/services/api/app/routes/search.py
from sqlalchemy.orm import selectinload
from ..db.query_optimizations import query_with_monitoring

@query_with_monitoring("search.hybrid_search")
def hybrid_search(...):
    stmt = (
        select(Document)
        .options(selectinload(Document.passages))  # Eager load
        .where(...)
    )
    return session.scalars(stmt).all()
```

**2. Document Detail**
```python
# theo/services/api/app/routes/documents.py
@router.get("/{document_id}")
def get_document(document_id: str, session: Session = Depends(get_session)):
    stmt = select(Document).options(selectinload(Document.passages))
    doc = session.scalars(stmt).where(Document.id == document_id).first()
    return document_to_dto(doc)
```

**3. Discovery Listing**
```python
# theo/services/api/app/routes/discoveries.py
@router.get("/")
def list_discoveries(
    user_id: str,
    limit: int = 100,  # Add pagination
    session: Session = Depends(get_session)
):
    # Limit results
```

### Success Criteria
- [ ] Search: 2 queries instead of 1+N
- [ ] Document detail: 1-2 queries instead of 1+N
- [ ] Monitoring decorators added
- [ ] No breaking changes to API

---

## Task F3: Wire Gap Engine into Discovery Service (3-4 hours)

**Original**: TASK_002  
**Goal**: Complete gap detection integration

**Note**: Gap engine already exists at `theo/domain/discoveries/gap_engine.py` ✅

### Implementation

**1. Update DiscoveryService**
```python
# theo/services/api/app/discoveries/service.py
from theo.domain.discoveries.gap_engine import GapDiscoveryEngine

class DiscoveryService:
    def __init__(
        self,
        session: Session,
        document_repo: DocumentRepository,
        discovery_repo: DiscoveryRepository,
    ):
        self.session = session
        self.document_repo = document_repo
        self.discovery_repo = discovery_repo
        self.gap_engine = GapDiscoveryEngine()  # Initialize
    
    def refresh_user_discoveries(self, user_id: str) -> list[DiscoveryDTO]:
        # Get documents
        documents = self.document_repo.list_with_embeddings(user_id)
        
        # Run gap detection
        gaps = self.gap_engine.detect(documents)
        
        # Convert to DiscoveryDTO and persist
        for gap in gaps:
            discovery = DiscoveryDTO(
                user_id=user_id,
                discovery_type="gap",
                title=gap.title,
                description=gap.description,
                confidence=gap.confidence,
                relevance_score=gap.relevance_score,
                metadata=dict(gap.metadata),
            )
            self.discovery_repo.create(discovery)
        
        # ... existing pattern detection, contradiction detection ...
        
        return discoveries
```

**2. Test Integration**
```python
# tests/domain/discoveries/test_gap_engine_integration.py
def test_gap_detection_in_service():
    # Setup
    service = DiscoveryService(session, doc_repo, disc_repo)
    
    # Execute
    discoveries = service.refresh_user_discoveries("test_user")
    
    # Assert
    gap_discoveries = [d for d in discoveries if d.discovery_type == "gap"]
    assert len(gap_discoveries) > 0
    assert all(d.confidence > 0 for d in gap_discoveries)
```

**3. Verify in UI**
- Navigate to `/discoveries`
- Should see gap-type discoveries appear
- Check metadata contains `reference_topic`, `missing_keywords`

### Success Criteria
- [ ] GapDiscoveryEngine integrated into refresh cycle
- [ ] Gaps persist to discoveries table
- [ ] Gaps appear in Discovery Feed UI
- [ ] Unit tests pass
- [ ] Performance: <5 seconds for 100 documents

---

## When to Complete These

### Option A: Complete Now (Recommended)
**Pros**: Clean foundation, catches issues early  
**Cons**: Delays MVP start by ~6 hours  
**Best if**: You want a rock-solid base

### Option B: Skip and Return Later
**Pros**: Start MVP immediately  
**Cons**: Might hit performance issues or gaps during MVP  
**Best if**: You want to move fast and iterate

### Option C: Interleave
**Pros**: Balance speed and quality  
**Cons**: Context switching  
**Best if**: You're pragmatic

**Recommendation**: Do F1 (30min validation) now, skip F2-F3 initially, return to them if you hit issues during MVP.

---

## Post-Completion Checklist

- [ ] F1: Architecture tests passing
- [ ] F2: Query optimizations in place (optional)
- [ ] F3: Gap engine integrated (optional)
- [ ] All tests green
- [ ] No regressions
- [ ] Documentation updated

**After foundation complete → Start CS-001 (Reasoning Timeline)**

---

## Quick Reference

- **F1 Commands**: `pytest tests/architecture/ -v`
- **F2 Pattern**: Add `selectinload()` to queries
- **F3 File**: `theo/services/api/app/discoveries/service.py`
- **Skip to MVP**: Go straight to `COGNITIVE_SCHOLAR_HANDOFF.md` → CS-001

---

**Estimated Total Time**: 4-6 hours (or 30min if you just do F1)
