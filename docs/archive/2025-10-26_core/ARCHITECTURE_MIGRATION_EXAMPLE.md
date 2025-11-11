> **Archived on 2025-10-26**

# Architecture Migration Example

This document demonstrates how to migrate existing code to use the new architectural patterns (DTOs, repositories, error handling, versioning).

## Before: Tightly Coupled Service

```python
# theo/infrastructure/api/app/routes/discoveries_old.py (OLD PATTERN)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

# Direct ORM import (BAD - adapter leakage)
from theo.adapters.persistence.models import Discovery

from theo.application.facades.database import get_session

router = APIRouter()

@router.get("/discoveries")
def list_discoveries(
    user_id: str,
    viewed: bool | None = None,
    session: Session = Depends(get_session),
):
    """List discoveries - OLD PATTERN."""
    
    # Direct SQLAlchemy query (BAD - no abstraction)
    stmt = select(Discovery).where(Discovery.user_id == user_id)
    if viewed is not None:
        stmt = stmt.where(Discovery.viewed == viewed)
    
    results = session.scalars(stmt).all()
    
    # Returns ORM models directly (BAD - adapter leakage)
    return [
        {
            "id": d.id,
            "title": d.title,
            "confidence": d.confidence,
            # ... manual serialization
        }
        for d in results
    ]

@router.post("/discoveries/{discovery_id}/view")
def mark_viewed(
    discovery_id: int,
    user_id: str,
    session: Session = Depends(get_session),
):
    """Mark discovery as viewed - OLD PATTERN."""
    
    # Direct database manipulation (BAD - no abstraction)
    discovery = session.get(Discovery, discovery_id)
    if not discovery or discovery.user_id != user_id:
        # Inconsistent error response (BAD)
        return {"error": "Not found"}, 404
    
    discovery.viewed = True
    session.commit()
    
    return {"status": "ok"}
```

## After: Clean Hexagonal Architecture

```python
# theo/infrastructure/api/app/routes/discoveries.py (NEW PATTERN)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# Application layer imports (GOOD - no adapter dependencies)
from theo.application.dtos import DiscoveryDTO, DiscoveryListFilters
from theo.application.repositories import DiscoveryRepository
from theo.domain.errors import NotFoundError

# Adapter factory (GOOD - dependency injection)
from theo.adapters.persistence.discovery_repository import SQLAlchemyDiscoveryRepository
from theo.application.facades.database import get_session

# API versioning (GOOD)
from ..versioning import get_version_manager

version_manager = get_version_manager()
v1 = version_manager.register_version("1.0", is_default=True)

router = APIRouter()

# Dependency injection for repository
def get_discovery_repo(session: Session = Depends(get_session)) -> DiscoveryRepository:
    """Factory for discovery repository."""
    return SQLAlchemyDiscoveryRepository(session)

@router.get("/discoveries")
def list_discoveries(
    user_id: str,
    viewed: bool | None = None,
    min_confidence: float | None = None,
    repo: DiscoveryRepository = Depends(get_discovery_repo),
) -> list[DiscoveryDTO]:
    """List discoveries - NEW PATTERN.
    
    Returns DTOs from repository, not ORM models.
    """
    
    # Use repository interface (GOOD - abstraction)
    filters = DiscoveryListFilters(
        user_id=user_id,
        viewed=viewed,
        min_confidence=min_confidence,
    )
    
    # Repository returns DTOs (GOOD - no ORM leakage)
    return repo.list(filters)

@router.post("/discoveries/{discovery_id}/view")
def mark_viewed(
    discovery_id: int,
    user_id: str,
    repo: DiscoveryRepository = Depends(get_discovery_repo),
) -> DiscoveryDTO:
    """Mark discovery as viewed - NEW PATTERN.
    
    Raises domain errors that are automatically mapped to HTTP responses.
    """
    
    # Repository handles database logic (GOOD)
    # Domain error raised if not found (GOOD - consistent errors)
    try:
        return repo.mark_viewed(discovery_id, user_id)
    except LookupError:
        # Convert to domain error for standard response
        raise NotFoundError("Discovery", discovery_id)

# Register with versioning (GOOD)
v1.include_router(router, prefix="/discoveries", tags=["discoveries"])
```

## Testing: Before vs After

### Before: Difficult Integration Test

```python
# tests/api/test_discoveries_old.py (OLD PATTERN)

def test_list_discoveries_old(api_engine):
    """Test required full database setup."""
    
    # Create database schema
    Base.metadata.create_all(api_engine)
    
    # Manual ORM setup
    session = Session(api_engine)
    discovery = Discovery(
        user_id="test",
        discovery_type="pattern",
        title="Test",
        confidence=0.8,
        # ... many fields
    )
    session.add(discovery)
    session.commit()
    
    # Test with TestClient
    client = TestClient(app)
    response = client.get("/discoveries?user_id=test")
    
    assert response.status_code == 200
    # Manual validation of response structure
```

### After: Easy Unit Test

```python
# tests/application/repositories/test_discovery_repository.py (NEW PATTERN)

from unittest.mock import Mock
from theo.application.dtos import DiscoveryDTO, DiscoveryListFilters
from theo.adapters.persistence.discovery_repository import SQLAlchemyDiscoveryRepository

def test_list_discoveries_unit():
    """Pure unit test without database."""
    
    # Mock the session
    mock_session = Mock()
    mock_session.scalars.return_value.all.return_value = [
        # Mock ORM objects
    ]
    
    # Test repository in isolation
    repo = SQLAlchemyDiscoveryRepository(mock_session)
    filters = DiscoveryListFilters(user_id="test", viewed=False)
    
    results = repo.list(filters)
    
    # Verify behavior
    assert len(results) > 0
    assert isinstance(results[0], DiscoveryDTO)
    assert results[0].user_id == "test"
```

### After: Fast Integration Test

```python
# tests/api/test_discoveries.py (NEW PATTERN)

def test_list_discoveries_integration(api_engine):
    """Integration test with repository abstraction."""
    
    # Use repository to setup test data (FAST)
    session = Session(api_engine)
    repo = SQLAlchemyDiscoveryRepository(session)
    
    # Create via repository (clean interface)
    dto = DiscoveryDTO(
        id=1,
        user_id="test",
        discovery_type="pattern",
        title="Test",
        # ... only DTO fields
    )
    repo.create(dto)
    session.commit()
    
    # Test API endpoint
    client = TestClient(app)
    response = client.get("/api/v1/discoveries?user_id=test")
    
    assert response.status_code == 200
    # Response is auto-validated by Pydantic
```

## Error Handling: Before vs After

### Before: Inconsistent Errors

```python
# Multiple error formats (BAD)

# Format 1
if not found:
    return {"error": "not found"}, 404

# Format 2
if not found:
    raise HTTPException(status_code=404, detail="Not found")

# Format 3
if not found:
    return JSONResponse({"message": "Missing"}, status_code=404)
```

### After: Standardized Errors

```python
# One consistent pattern (GOOD)

from theo.domain.errors import NotFoundError, ValidationError

# In business logic
if not document:
    raise NotFoundError("Document", document_id)

if invalid_input:
    raise ValidationError("Invalid format", field="email")

# Middleware automatically converts to:
# {
#   "error": {
#     "type": "NotFoundError",
#     "code": "NotFoundError",
#     "message": "Document with ID 'abc' not found",
#     "resource_type": "Document",
#     "resource_id": "abc"
#   },
#   "trace_id": "..."
# }
```

## Query Optimization: Before vs After

### Before: N+1 Problem

```python
# OLD: N+1 queries
def list_documents_with_passages(session, user_id):
    docs = session.query(Document).filter_by(collection=user_id).all()
    
    for doc in docs:
        # QUERY PER DOCUMENT!
        passages = doc.passages
        print(f"Doc {doc.id} has {len(passages)} passages")
    
    return docs
```

### After: Optimized Loading

```python
# NEW: 2 queries total
from sqlalchemy.orm import selectinload

def list_documents_with_passages(session, user_id):
    stmt = (
        select(Document)
        .where(Document.collection == user_id)
        .options(selectinload(Document.passages))  # Eager load
    )
    
    docs = session.scalars(stmt).all()
    
    for doc in docs:
        # NO ADDITIONAL QUERIES!
        passages = doc.passages
        print(f"Doc {doc.id} has {len(passages)} passages")
    
    return docs
```

### After: With Monitoring

```python
# NEW: Optimized + monitored
from theo.services.api.app.db.query_optimizations import (
    query_with_monitoring,
    with_eager_loading,
)

@query_with_monitoring("document.list_with_passages")
def list_documents_with_passages(session, user_id):
    # Automatic metrics:
    # - document.list_with_passages.duration_seconds
    # - document.list_with_passages.result_count
    
    stmt = (
        select(Document)
        .where(Document.collection == user_id)
        .options(*with_eager_loading(Document, Document.passages))
    )
    
    return session.scalars(stmt).all()
```

## Migration Checklist

### Step 1: Add DTOs for Your Domain
- [ ] Create `theo/application/dtos/your_domain.py`
- [ ] Define immutable dataclasses with type hints
- [ ] Export from `theo/application/dtos/__init__.py`

### Step 2: Add Mappers
- [ ] Add mapper functions to `theo/adapters/persistence/mappers.py`
- [ ] Implement `model_to_dto()` and `dto_to_model()`
- [ ] Handle nullable fields and type conversions

### Step 3: Create Repository Interface
- [ ] Create `theo/application/repositories/your_repository.py`
- [ ] Define abstract methods using DTOs
- [ ] Document expected behavior

### Step 4: Implement Repository
- [ ] Create `theo/adapters/persistence/your_repository.py`
- [ ] Implement interface using SQLAlchemy
- [ ] Use mappers for conversions
- [ ] Add query optimizations

### Step 5: Update Routes
- [ ] Replace direct ORM imports with DTOs
- [ ] Inject repository via Depends()
- [ ] Use domain errors for failures
- [ ] Register with API versioning

### Step 6: Add Tests
- [ ] Unit tests for repository (mock session)
- [ ] Integration tests with test database
- [ ] API endpoint tests via TestClient
- [ ] Add to architecture boundary tests

## Common Pitfalls

### ❌ Pitfall 1: Returning ORM Models from Routes
```python
# BAD
@router.get("/discoveries")
def list_discoveries(session: Session) -> list[Discovery]:
    return session.query(Discovery).all()  # ORM model exposed!
```

✅ **Fix**: Return DTOs
```python
# GOOD
@router.get("/discoveries")
def list_discoveries(repo: DiscoveryRepository) -> list[DiscoveryDTO]:
    return repo.list(filters)  # DTOs returned
```

### ❌ Pitfall 2: Repository Returning ORM Models
```python
# BAD
class MyRepository:
    def get_all(self) -> list[MyModel]:
        return self.session.query(MyModel).all()  # ORM leak!
```

✅ **Fix**: Use Mappers
```python
# GOOD
class MyRepository:
    def get_all(self) -> list[MyDTO]:
        results = self.session.query(MyModel).all()
        return [model_to_dto(r) for r in results]  # DTOs returned
```

### ❌ Pitfall 3: N+1 Queries
```python
# BAD
docs = session.query(Document).all()
for doc in docs:
    print(doc.passages)  # Query per document!
```

✅ **Fix**: Eager Loading
```python
# GOOD
from sqlalchemy.orm import selectinload

docs = session.query(Document).options(
    selectinload(Document.passages)
).all()
```

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Coupling** | Service → ORM | Service → DTOs → ORM |
| **Testing** | Requires database | Mock repository |
| **Errors** | 3+ formats | 1 standard format |
| **Queries** | N+1 problems | Eager loading |
| **Versioning** | None | URL-based v1, v2 |
| **Monitoring** | Manual logging | Auto metrics |

---

**Next Steps**: Start with high-traffic endpoints (search, discoveries) and migrate incrementally.
