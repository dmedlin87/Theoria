# Implementation Context for AI Agents

This document provides complete context for AI agents to continue development of the Theoria project.

---

## Project Overview

**Theoria** is an evidence-first theological research platform combining RAG (Retrieval-Augmented Generation), auto-discovery, and agent-based reasoning to help users explore biblical texts and theological documents.

**Tech Stack:**
- Frontend: Next.js 14 (App Router), React, TypeScript
- Backend: FastAPI, Python 3.12
- Database: PostgreSQL + pgvector
- AI: OpenAI GPT-4, transformers (HuggingFace), scikit-learn
- Deployment: Docker, Docker Compose

---

## Architecture Patterns

### Hexagonal Architecture
The codebase follows hexagonal (ports & adapters) architecture:

```
theo/
├── domain/           # Core business logic (pure Python)
│   ├── discoveries/  # Discovery engines
│   └── repositories/ # Repository interfaces
├── application/      # Use cases and facades
│   └── facades/      # Database, settings, runtime
├── adapters/         # External integrations
│   └── research/     # Research providers
└── services/
    ├── api/          # FastAPI application
    └── web/          # Next.js frontend
```

**Key Principles:**
- Domain layer has no external dependencies
- Application layer orchestrates domain logic
- Adapters handle external systems
- Services expose functionality via APIs/UI

### Discovery Engine Pattern

All discovery engines follow this pattern:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class XyzDiscovery:
    """Discovery result with metadata."""
    title: str
    description: str
    confidence: float  # 0.0 - 1.0
    relevance_score: float  # 0.0 - 1.0
    metadata: dict[str, object]

class XyzDiscoveryEngine:
    """Engine for detecting XYZ patterns."""
    
    def __init__(self, *, param1: type = default):
        """Initialize with configuration."""
        self.param1 = param1
    
    def detect(self, documents: Sequence[DocumentEmbedding]) -> list[XyzDiscovery]:
        """Detect patterns and return discoveries."""
        # 1. Validate input
        if len(documents) < min_required:
            return []
        
        # 2. Run detection algorithm
        results = self._run_detection(documents)
        
        # 3. Filter and rank
        filtered = [r for r in results if r.confidence >= threshold]
        filtered.sort(key=lambda x: x.confidence, reverse=True)
        
        # 4. Return top N
        return filtered[:max_results]
```

**Integration into DiscoveryService:**

```python
# theo/services/api/app/discoveries/service.py

def refresh_user_discoveries(self, user_id: str) -> list[Discovery]:
    documents = self._load_document_embeddings(user_id)
    
    # Run all engines
    pattern_discoveries = self.pattern_engine.detect(documents)
    contradiction_discoveries = self.contradiction_engine.detect(documents)
    xyz_discoveries = self.xyz_engine.detect(documents)  # Add new engine
    
    # Delete old discoveries
    self.session.execute(
        delete(Discovery).where(
            Discovery.user_id == user_id,
            Discovery.discovery_type.in_([
                DiscoveryType.PATTERN.value,
                DiscoveryType.CONTRADICTION.value,
                DiscoveryType.XYZ.value,  # Add new type
            ])
        )
    )
    
    # Persist all discoveries
    all_discoveries = (
        pattern_discoveries + 
        contradiction_discoveries + 
        xyz_discoveries  # Add new discoveries
    )
    
    for discovery in all_discoveries:
        record = Discovery(
            user_id=user_id,
            discovery_type=discovery.type,
            title=discovery.title,
            description=discovery.description,
            confidence=float(discovery.confidence),
            relevance_score=float(discovery.relevance_score),
            viewed=False,
            meta=dict(discovery.metadata),
            created_at=datetime.now(UTC),
        )
        self.session.add(record)
    
    self.session.commit()
    return all_discoveries
```

---

## Code Style & Conventions

### Python

**Type Hints:**
```python
# Always use type hints
def function(param: str, optional: int | None = None) -> list[str]:
    pass

# Use from __future__ import annotations for forward refs
from __future__ import annotations
```

**Imports:**
```python
# Standard library
from __future__ import annotations
import logging
from datetime import UTC, datetime
from typing import Sequence

# Third-party
import numpy as np
from sqlalchemy import select

# Local
from theo.domain.discoveries import DiscoveryType
from ..models import Discovery
```

**Docstrings:**
```python
def function(param: str) -> int:
    """Short description.
    
    Longer description if needed.
    
    Args:
        param: Description of parameter
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When something goes wrong
    """
```

**Error Handling:**
```python
# Specific exceptions
try:
    result = risky_operation()
except SpecificError as exc:
    logger.exception("Context about what failed")
    raise CustomError("User-friendly message") from exc
```

### TypeScript/React

**Component Structure:**
```tsx
// Use CSS modules
import styles from './Component.module.css';

interface ComponentProps {
  required: string;
  optional?: number;
}

export function Component({ required, optional = 0 }: ComponentProps) {
  const [state, setState] = useState<string>('');
  
  return (
    <div className={styles.container}>
      {/* Content */}
    </div>
  );
}
```

**API Calls:**
```tsx
// Use fetch with proper error handling
async function fetchData() {
  try {
    const response = await fetch('/api/endpoint', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch:', error);
    throw error;
  }
}
```

---

## Testing Patterns

### Unit Tests

```python
# tests/domain/discoveries/test_xyz_engine.py

import pytest
from theo.domain.discoveries import XyzDiscoveryEngine, DocumentEmbedding

@pytest.fixture
def sample_documents():
    """Fixture providing test documents."""
    return [
        DocumentEmbedding(
            document_id="doc1",
            title="Test Document",
            abstract="Test abstract",
            topics=["test"],
            verse_ids=[43001001],
            embedding=[0.1] * 768,
            metadata={},
        ),
    ]

def test_engine_initialization():
    """Test engine initializes correctly."""
    engine = XyzDiscoveryEngine()
    assert engine.param1 == expected_default

def test_detect_with_valid_input(sample_documents):
    """Test detection with valid documents."""
    engine = XyzDiscoveryEngine()
    discoveries = engine.detect(sample_documents)
    
    assert len(discoveries) > 0
    assert discoveries[0].confidence >= 0.0
    assert discoveries[0].confidence <= 1.0

def test_detect_with_insufficient_documents():
    """Test detection fails gracefully with too few documents."""
    engine = XyzDiscoveryEngine()
    discoveries = engine.detect([])
    
    assert discoveries == []

@pytest.mark.slow
def test_detect_integration(sample_documents):
    """Integration test requiring external resources."""
    # Tests marked 'slow' can be skipped in CI
    pass
```

### Integration Tests

```python
# tests/api/test_discovery_integration.py

def test_discovery_refresh_end_to_end(session, user_id):
    """Test full discovery refresh flow."""
    # 1. Setup: Create test documents
    documents = create_test_documents(session, user_id)
    
    # 2. Execute: Refresh discoveries
    discovery_repo = SQLAlchemyDiscoveryRepository(session)
    document_repo = SQLAlchemyDocumentRepository(session)
    service = DiscoveryService(discovery_repo, document_repo)
    discoveries = service.refresh_user_discoveries(user_id)
    
    # 3. Assert: Verify results
    assert len(discoveries) > 0
    
    # 4. Verify database state
    db_discoveries = session.query(Discovery).filter_by(user_id=user_id).all()
    assert len(db_discoveries) == len(discoveries)
```

---

## Database Patterns

### Models

```python
# theo/services/api/app/db/models.py

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB
from .base import Base

class Discovery(Base):
    __tablename__ = "discoveries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    discovery_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    relevance_score = Column(Float, nullable=False, default=0.0)
    viewed = Column(Boolean, nullable=False, default=False, index=True)
    user_reaction = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    meta = Column(JSONB, nullable=True)  # Type-specific metadata
```

### Queries

```python
# Use SQLAlchemy 2.0 style
from sqlalchemy import select, delete

# Select
stmt = select(Discovery).where(
    Discovery.user_id == user_id,
    Discovery.viewed == False,
).order_by(Discovery.created_at.desc())
results = session.scalars(stmt).all()

# Delete
stmt = delete(Discovery).where(
    Discovery.user_id == user_id,
    Discovery.discovery_type == "pattern",
)
session.execute(stmt)
session.commit()
```

---

## API Patterns

### FastAPI Routes

```python
# theo/services/api/app/routes/xyz.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session
from ..models.xyz import XyzRequest, XyzResponse
from ..security import Principal, require_principal

router = APIRouter()

@router.get("/", response_model=list[XyzResponse])
def list_xyz(
    filter_param: str | None = None,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
) -> list[XyzResponse]:
    """List XYZ resources."""
    user_id = principal["subject"]
    
    # Query database
    results = query_xyz(session, user_id, filter_param)
    
    # Convert to response models
    return [XyzResponse.model_validate(r) for r in results]

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_xyz(
    request: XyzRequest,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
) -> XyzResponse:
    """Create new XYZ resource."""
    user_id = principal["subject"]
    
    # Validate and create
    xyz = create_xyz_resource(session, user_id, request)
    
    return XyzResponse.model_validate(xyz)
```

### Pydantic Models

```python
# theo/services/api/app/models/xyz.py

from pydantic import BaseModel, Field

class XyzRequest(BaseModel):
    """Request model for creating XYZ."""
    name: str = Field(..., min_length=1, max_length=255)
    optional_field: int | None = Field(None, ge=0)

class XyzResponse(BaseModel):
    """Response model for XYZ."""
    id: int
    name: str
    created_at: str
    
    model_config = {"from_attributes": True}  # Enable ORM mode
```

---

## Common Pitfalls & Solutions

### 1. Model Loading Performance

**Problem:** Loading large ML models on every request

**Solution:** Lazy loading with caching
```python
class Engine:
    def __init__(self):
        self._model = None
    
    def _load_model(self):
        if self._model is None:
            self._model = load_expensive_model()
```

### 2. Memory Issues with Large Corpora

**Problem:** Loading all embeddings into memory

**Solution:** Batch processing and streaming
```python
def process_documents(documents):
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        yield process_batch(batch)
```

### 3. Database Connection Leaks

**Problem:** Not closing sessions properly

**Solution:** Use context managers
```python
with get_session() as session:
    # Work with session
    pass  # Automatically closed
```

### 4. Frontend State Management

**Problem:** Prop drilling and scattered state

**Solution:** Use React Context or state management library
```tsx
// Create context
const DiscoveryContext = createContext<DiscoveryContextType | null>(null);

// Provider
export function DiscoveryProvider({ children }) {
  const [discoveries, setDiscoveries] = useState([]);
  return (
    <DiscoveryContext.Provider value={{ discoveries, setDiscoveries }}>
      {children}
    </DiscoveryContext.Provider>
  );
}

// Consumer
function Component() {
  const { discoveries } = useContext(DiscoveryContext);
}
```

---

## Development Workflow

### 1. Create Feature Branch
```bash
git checkout -b feature/gap-analysis
```

### 2. Implement Feature
- Write tests first (TDD)
- Implement domain logic
- Integrate into service layer
- Add API endpoints
- Update frontend (if needed)
- Write documentation

### 3. Run Tests
```bash
# Unit tests
pytest tests/domain/discoveries/test_gap_engine.py -v

# Integration tests
pytest tests/api/test_discovery_integration.py -v

# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=theo --cov-report=html
```

### 4. Type Checking
```bash
mypy theo/
```

### 5. Linting
```bash
ruff check theo/
ruff format theo/
```

### 6. Manual Testing
```bash
# Start services
.\start-theoria.ps1

# Test API
curl http://localhost:8000/api/discoveries

# Test frontend
# Open http://localhost:3000/discoveries
```

### 7. Documentation
- Update relevant .md files
- Add docstrings to new functions
- Update HANDOFF documents if needed

---

## Environment Setup

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/theoria

# OpenAI
OPENAI_API_KEY=sk-...

# Optional: Discovery configuration
THEORIA_DISCOVERY_INTERVAL=30
THEORIA_NLI_MODEL=microsoft/deberta-v3-base-mnli
THEORIA_CONTRADICTION_THRESHOLD=0.7
```

### Local Development

```bash
# Install dependencies
pip install ".[api]" -c constraints/api-constraints.txt
pip install ".[ml]" -c constraints/ml-constraints.txt
pip install ".[dev]" -c constraints/dev-constraints.txt

# Setup database
docker-compose up -d postgres

# Run migrations (ensures idx_passages_embedding_null, idx_documents_updated_at, idx_passages_document_id)
python -m theo.services.api.app.db.run_sql_migrations

# Start API
cd theo/services/api
uvicorn app.main:app --reload

# Start frontend (separate terminal)
cd theo/services/web
npm install
npm run dev
```

---

## Debugging Tips

### 1. Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. Use IPython for Interactive Debugging
```python
# Add breakpoint
import IPython; IPython.embed()
```

### 3. Check Database State
```bash
# Connect to database
psql $DATABASE_URL

# Query discoveries
SELECT id, discovery_type, title, confidence FROM discoveries WHERE user_id = 'test';
```

### 4. Inspect API Requests
```bash
# Use httpie for better formatting
http GET localhost:8000/api/discoveries Authorization:"Bearer $TOKEN"
```

### 5. Frontend Debugging
```tsx
// Use React DevTools
console.log('State:', state);

// Network tab in browser DevTools
// Check API responses
```

---

## Key Dependencies

### Python
- `fastapi` - Web framework
- `sqlalchemy` - ORM
- `pydantic` - Data validation
- `transformers` - HuggingFace models
- `torch` - PyTorch
- `scikit-learn` - ML algorithms
- `numpy` - Numerical computing
- `apscheduler` - Task scheduling

### TypeScript/React
- `next` - React framework
- `react` - UI library
- `typescript` - Type safety
- `lucide-react` - Icons

---

## Resources

### Documentation
- `docs/INDEX.md` - Master documentation index
- `docs/AGENT_AND_PROMPTING_GUIDE.md` - Agent architecture
- `docs/DISCOVERY_FEATURE.md` - Discovery system spec
- `HANDOFF_NEXT_PHASE.md` - Development roadmap
- `HANDOFF_SESSION_2025_10_15.md` - Latest session summary

### Code Examples
- `theo/domain/discoveries/engine.py` - Pattern detection (reference)
- `theo/domain/discoveries/contradiction_engine.py` - Contradiction detection (reference)
- `theo/services/api/app/discoveries/service.py` - Service integration (reference)

### External Resources
- FastAPI docs: https://fastapi.tiangolo.com
- SQLAlchemy docs: https://docs.sqlalchemy.org
- HuggingFace docs: https://huggingface.co/docs
- Next.js docs: https://nextjs.org/docs

---

**Last Updated:** 2025-01-15  
**For Questions:** See documentation in `docs/` directory
