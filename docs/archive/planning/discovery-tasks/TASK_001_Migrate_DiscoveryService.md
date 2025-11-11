# TASK 001: Migrate DiscoveryService to New Architecture

**Priority**: ⭐⭐⭐ HIGH  
**Estimated Time**: 2-3 hours  
**Dependencies**: Architecture improvements complete (✅ Done)  
**Status**: Ready to start

---

## 🎯 Objective

Migrate `DiscoveryService` from direct ORM usage to the new repository pattern, demonstrating the architecture migration path and creating a template for future migrations.

---

## 📋 Why This Matters

1. **Validates the pattern stack** - Shows DTOs, repositories, and use cases working in production code
2. **Creates migration blueprint** - Other services can follow this example
3. **Improves testability** - Can mock repositories instead of database
4. **Reduces technical debt** - Eliminates ORM leakage from service layer
5. **Performance boost** - Enables query optimizations

---

## 📂 Files to Create

### 1. Document Repository Interface
**File**: `theo/application/repositories/document_repository.py`

```python
"""Repository interface for document operations."""

from abc import ABC, abstractmethod
from theo.application.dtos import DocumentDTO, DocumentSummaryDTO
from theo.domain.discoveries import DocumentEmbedding


class DocumentRepository(ABC):
    """Abstract repository for document persistence."""
    
    @abstractmethod
    def list_with_embeddings(self, user_id: str) -> list[DocumentEmbedding]:
        """Load documents with averaged embeddings for discovery processing."""
        ...
    
    @abstractmethod
    def get_by_id(self, document_id: str) -> DocumentDTO | None:
        """Get single document by ID."""
        ...
    
    @abstractmethod
    def list_summaries(
        self,
        user_id: str,
        limit: int | None = None,
    ) -> list[DocumentSummaryDTO]:
        """List document summaries without passages."""
        ...
```

### 2. SQLAlchemy Document Repository
**File**: `theo/adapters/persistence/document_repository.py`

```python
"""SQLAlchemy implementation of DocumentRepository."""

from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from theo.application.repositories.document_repository import DocumentRepository
from theo.application.dtos import DocumentDTO, DocumentSummaryDTO
from theo.domain.discoveries import DocumentEmbedding
from .models import Document, Passage
from .mappers import document_to_dto, document_summary_to_dto
import numpy as np


class SQLAlchemyDocumentRepository(DocumentRepository):
    """Document repository using SQLAlchemy."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def list_with_embeddings(self, user_id: str) -> list[DocumentEmbedding]:
        """Load documents with averaged embeddings."""
        # Use eager loading to prevent N+1
        stmt = (
            select(Document)
            .where(Document.collection == user_id)
            .options(selectinload(Document.passages))
        )
        documents = self.session.scalars(stmt).all()
        
        result = []
        for doc in documents:
            # Average passage embeddings
            vectors = [p.embedding for p in doc.passages if p.embedding]
            if not vectors:
                continue
            
            averaged = self._average_vectors(vectors)
            if not averaged:
                continue
            
            # Extract verse IDs
            verse_ids = set()
            for passage in doc.passages:
                if passage.osis_verse_ids:
                    verse_ids.update(passage.osis_verse_ids)
            
            # Extract topics
            topics = self._extract_topics(doc.topics)
            
            result.append(DocumentEmbedding(
                document_id=doc.id,
                title=doc.title or "Untitled",
                abstract=doc.abstract,
                topics=topics,
                verse_ids=sorted(verse_ids),
                embedding=averaged,
                metadata={"keywords": topics, "documentId": doc.id},
            ))
        
        return result
    
    def get_by_id(self, document_id: str) -> DocumentDTO | None:
        """Get document by ID with passages."""
        doc = self.session.get(Document, document_id)
        if not doc:
            return None
        return document_to_dto(doc)
    
    def list_summaries(
        self,
        user_id: str,
        limit: int | None = None,
    ) -> list[DocumentSummaryDTO]:
        """List document summaries."""
        stmt = select(Document).where(Document.collection == user_id)
        if limit:
            stmt = stmt.limit(limit)
        
        results = self.session.scalars(stmt).all()
        return [document_summary_to_dto(doc) for doc in results]
    
    @staticmethod
    def _average_vectors(vectors: list) -> list[float]:
        """Average embedding vectors."""
        array = np.array(vectors, dtype=float)
        if not np.isfinite(array).all():
            array = array[np.isfinite(array).all(axis=1)]
        if len(array) == 0:
            return []
        return array.mean(axis=0).tolist()
    
    @staticmethod
    def _extract_topics(topics_field) -> list[str]:
        """Extract topics from various formats."""
        if isinstance(topics_field, list):
            return [str(t) for t in topics_field if isinstance(t, str)]
        return []
```

### 3. Update Use Case to Use Repositories
**File**: `theo/infrastructure/api/app/use_cases/refresh_discoveries.py` (modify)

Update the `execute()` method to accept repositories instead of raw documents:

```python
def execute(
    self,
    user_id: str,
    document_repo: DocumentRepository,
) -> list[DiscoveryDTO]:
    """Execute discovery refresh using repositories."""
    
    # Load documents via repository (with optimizations)
    documents = document_repo.list_with_embeddings(user_id)
    
    # Rest of logic stays the same...
```

---

## 📝 Files to Modify

### 1. Update DiscoveryService
**File**: `theo/infrastructure/api/app/discoveries/service.py`

**Changes needed**:
1. Remove direct ORM imports (`Discovery`, `Document`, `Passage`)
2. Inject repositories via constructor
3. Use repositories instead of direct queries
4. Return DTOs instead of ORM models

**Before**:
```python
from theo.adapters.persistence.models import Discovery, Document, Passage

class DiscoveryService:
    def __init__(self, session: Session):
        self.session = session
    
    def refresh_user_discoveries(self, user_id: str):
        documents = self._load_document_embeddings(user_id)
        # Direct ORM manipulation...
```

**After**:
```python
from theo.application.repositories import DiscoveryRepository, DocumentRepository
from theo.application.dtos import DiscoveryDTO

class DiscoveryService:
    def __init__(
        self,
        discovery_repo: DiscoveryRepository,
        document_repo: DocumentRepository,
    ):
        self.discovery_repo = discovery_repo
        self.document_repo = document_repo
    
    def refresh_user_discoveries(self, user_id: str) -> list[DiscoveryDTO]:
        documents = self.document_repo.list_with_embeddings(user_id)
        # Use repository methods...
```

### 2. Update Routes
**File**: `theo/infrastructure/api/app/routes/discoveries.py`

Add dependency injection for repositories:

```python
from theo.adapters.persistence.discovery_repository import SQLAlchemyDiscoveryRepository
from theo.adapters.persistence.document_repository import SQLAlchemyDocumentRepository

def get_discovery_service(
    session: Session = Depends(get_session),
) -> DiscoveryService:
    """Factory for DiscoveryService with repository injection."""
    discovery_repo = SQLAlchemyDiscoveryRepository(session)
    document_repo = SQLAlchemyDocumentRepository(session)
    return DiscoveryService(discovery_repo, document_repo)

@router.post("/refresh")
def refresh_discoveries(
    user_id: str,
    service: DiscoveryService = Depends(get_discovery_service),
):
    return service.refresh_user_discoveries(user_id)
```

---

## 🧪 Testing Strategy

### 1. Create Repository Tests
**File**: `tests/application/repositories/test_document_repository.py`

```python
"""Unit tests for DocumentRepository."""

from unittest.mock import Mock
import numpy as np

def test_list_with_embeddings():
    """Test loading documents with averaged embeddings."""
    mock_session = Mock()
    # Setup mock to return documents with passages
    
    repo = SQLAlchemyDocumentRepository(mock_session)
    results = repo.list_with_embeddings("test_user")
    
    assert len(results) > 0
    assert isinstance(results[0], DocumentEmbedding)
    assert results[0].embedding is not None

def test_list_with_embeddings_eager_loading():
    """Verify eager loading prevents N+1 queries."""
    mock_session = Mock()
    repo = SQLAlchemyDocumentRepository(mock_session)
    
    repo.list_with_embeddings("test_user")
    
    # Verify selectinload was used
    call_args = mock_session.scalars.call_args
    # Assert eager loading in query
```

### 2. Update Service Tests
**File**: `tests/api/test_discovery_service.py`

```python
"""Test DiscoveryService with mocked repositories."""

from unittest.mock import Mock

def test_refresh_discoveries_with_mock_repos():
    """Test service using repository mocks (no database!)."""
    # Create mock repositories
    mock_discovery_repo = Mock()
    mock_document_repo = Mock()
    
    # Setup return values
    mock_document_repo.list_with_embeddings.return_value = [
        DocumentEmbedding(
            document_id="doc1",
            title="Test",
            abstract=None,
            topics=["theology"],
            verse_ids=[43001001],
            embedding=[0.1] * 768,
            metadata={},
        )
    ]
    
    # Test service
    service = DiscoveryService(mock_discovery_repo, mock_document_repo)
    results = service.refresh_user_discoveries("test_user")
    
    # Verify repositories were called
    mock_document_repo.list_with_embeddings.assert_called_once_with("test_user")
    mock_discovery_repo.delete_by_types.assert_called_once()
```

### 3. Integration Tests
**File**: `tests/api/test_discovery_integration.py`

Test with real repositories and database to ensure everything works end-to-end.

---

## ✅ Success Criteria

- [ ] `DocumentRepository` interface created
- [ ] SQLAlchemy implementation complete
- [ ] `DiscoveryService` migrated to use repositories
- [ ] No direct ORM imports in service layer
- [ ] All tests passing (unit + integration)
- [ ] Architecture tests pass (`pytest tests/architecture/`)
- [ ] Performance maintained or improved
- [ ] Documentation updated

---

## 📊 Performance Validation

Before/after metrics to capture:

```python
import time

# Before
start = time.perf_counter()
service.refresh_user_discoveries(user_id)
duration_before = time.perf_counter() - start

# After (should be similar or faster due to eager loading)
start = time.perf_counter()
service.refresh_user_discoveries(user_id)
duration_after = time.perf_counter() - start

print(f"Before: {duration_before:.3f}s")
print(f"After: {duration_after:.3f}s")
print(f"Improvement: {((duration_before - duration_after) / duration_before) * 100:.1f}%")
```

---

## 📚 References

- **Pattern Reference**: `theo/infrastructure/api/app/routes/discoveries_v1.py`
- **Migration Guide**: `docs/ARCHITECTURE_MIGRATION_EXAMPLE.md`
- **Architecture Guide**: `docs/ARCHITECTURE_IMPROVEMENTS.md`
- **Quick Start**: `QUICK_START_ARCHITECTURE.md`

---

## 🚨 Common Pitfalls

1. **Don't return ORM models** - Always convert to DTOs
2. **Remember eager loading** - Use `selectinload()` for relationships
3. **Test with mocks first** - Verify logic without database
4. **Check architecture tests** - Run `pytest tests/architecture/` frequently
5. **Document decisions** - Add notes to `ARCHITECTURE_MIGRATION_EXAMPLE.md`

---

## 📝 Post-Migration Checklist

- [ ] Document lessons learned
- [ ] Update migration guide with insights
- [ ] Create reusable patterns for next migration
- [ ] Measure and document performance improvements
- [ ] Update team on new patterns

---

**Next Task After Completion**: TASK_002 (Gap Analysis Engine)
