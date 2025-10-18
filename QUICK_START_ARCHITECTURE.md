# Quick Start: New Architecture Patterns

**5-Minute Guide** to using the improved architecture in Theoria.

---

## 🎯 What Changed?

1. **DTOs** - Service layer uses DTOs instead of ORM models
2. **Repositories** - Database access through abstract interfaces
3. **Domain Errors** - Consistent error responses across all endpoints
4. **API Versioning** - URL-based versioning for backward compatibility
5. **Query Optimization** - Tools to eliminate N+1 queries

---

## 🚀 Quick Examples

### ✅ Create a New Route (The Right Way)

```python
# theo/services/api/app/routes/my_feature.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from theo.application.dtos import DiscoveryDTO, DiscoveryListFilters
from theo.application.repositories import DiscoveryRepository
from theo.adapters.persistence.discovery_repository import SQLAlchemyDiscoveryRepository
from theo.application.facades.database import get_session
from theo.domain.errors import NotFoundError

router = APIRouter()

# Factory for dependency injection
def get_repo(session: Session = Depends(get_session)) -> DiscoveryRepository:
    return SQLAlchemyDiscoveryRepository(session)

# Clean route handler
@router.get("/my-discoveries")
def list_my_discoveries(
    user_id: str,
    repo: DiscoveryRepository = Depends(get_repo),
) -> list[DiscoveryDTO]:
    """List discoveries - works with DTOs, not ORM models."""
    filters = DiscoveryListFilters(user_id=user_id, viewed=False)
    return repo.list(filters)

# Errors are automatic
@router.get("/my-discoveries/{discovery_id}")
def get_discovery(
    discovery_id: int,
    user_id: str,
    repo: DiscoveryRepository = Depends(get_repo),
) -> DiscoveryDTO:
    """Get discovery - domain errors map to HTTP."""
    discovery = repo.get_by_id(discovery_id, user_id)
    if not discovery:
        raise NotFoundError("Discovery", discovery_id)  # → HTTP 404
    return discovery
```

### ✅ Write a Unit Test (No Database Needed!)

```python
# tests/my_feature/test_routes.py

from unittest.mock import Mock
from theo.application.dtos import DiscoveryDTO

def test_list_discoveries():
    """Test without database - just mock the repository."""
    # Create mock
    mock_repo = Mock()
    mock_repo.list.return_value = [
        DiscoveryDTO(
            id=1,
            user_id="test",
            discovery_type="pattern",
            title="Test",
            description="Test discovery",
            confidence=0.8,
            relevance_score=0.7,
            viewed=False,
            user_reaction=None,
            created_at=datetime.now(UTC),
            metadata={},
        )
    ]
    
    # Test your logic
    filters = DiscoveryListFilters(user_id="test")
    results = mock_repo.list(filters)
    
    assert len(results) == 1
    assert results[0].title == "Test"
```

### ✅ Optimize a Query (Eliminate N+1)

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from theo.services.api.app.db.query_optimizations import query_with_monitoring

@query_with_monitoring("document.list_with_passages")
def list_documents_optimized(session, user_id):
    """Loads documents + passages in 2 queries instead of 1+N."""
    stmt = (
        select(Document)
        .where(Document.collection == user_id)
        .options(selectinload(Document.passages))  # Eager load!
    )
    return session.scalars(stmt).all()
```

---

## 📋 Common Tasks

### Task: Add a New Domain Error

```python
# theo/domain/errors.py

class MyCustomError(DomainError):
    """My custom business error."""
    pass

# theo/services/api/app/error_handlers.py
# Update ERROR_STATUS_MAP
ERROR_STATUS_MAP = {
    MyCustomError: status.HTTP_418_IM_A_TEAPOT,
    # ...
}
```

### Task: Create a New Repository

```python
# 1. Define DTO
# theo/application/dtos/my_domain.py
@dataclass(frozen=True)
class MyEntityDTO:
    id: int
    name: str

# 2. Define interface
# theo/application/repositories/my_repository.py
class MyRepository(ABC):
    @abstractmethod
    def list(self) -> list[MyEntityDTO]: ...

# 3. Implement with SQLAlchemy
# theo/adapters/persistence/my_repository.py
class SQLAlchemyMyRepository(MyRepository):
    def __init__(self, session: Session):
        self.session = session
    
    def list(self) -> list[MyEntityDTO]:
        results = self.session.query(MyModel).all()
        return [model_to_dto(r) for r in results]
```

### Task: Add API Versioning to Routes

```python
# main.py - already done!
v1 = version_manager.register_version("1.0", is_default=True)

# Your route file
from theo.services.api.app.versioning import get_version_manager

v1 = get_version_manager().get_version("1.0")
v1.include_router(router, prefix="/my-feature", tags=["my-feature"])

# Now accessible at: /api/v1/my-feature
```

---

## 🎓 Learn More

| Document | Purpose |
|----------|---------|
| `docs/ARCHITECTURE_IMPROVEMENTS.md` | Full implementation guide |
| `docs/ARCHITECTURE_MIGRATION_EXAMPLE.md` | Before/after code examples |
| `examples/architecture_migration_step_by_step.py` | Step-by-step migration |
| `ARCHITECTURE_REVIEW_IMPLEMENTATION_SUMMARY.md` | Executive summary |

---

## ✨ Benefits You Get

✅ **Better Testing** - Mock repositories instead of databases  
✅ **Type Safety** - DTOs provide clear contracts  
✅ **Consistent Errors** - Standard JSON responses with trace IDs  
✅ **Performance** - Built-in query optimization tools  
✅ **Maintainability** - Clear layer boundaries  
✅ **Backward Compatible** - Old code still works  

---

## 🚨 Common Mistakes to Avoid

❌ **Don't** import ORM models in routes
```python
from theo.adapters.persistence.models import Discovery  # BAD
```

✅ **Do** use DTOs
```python
from theo.application.dtos import DiscoveryDTO  # GOOD
```

❌ **Don't** query database directly in routes
```python
session.query(Discovery).all()  # BAD
```

✅ **Do** use repositories
```python
repo.list(filters)  # GOOD
```

❌ **Don't** return different error formats
```python
return {"error": "not found"}, 404  # BAD
```

✅ **Do** use domain errors
```python
raise NotFoundError("Resource", id)  # GOOD → consistent JSON
```

---

**Ready to build?** Start with the reference implementation in `routes/discoveries_v1.py`! 🎉
