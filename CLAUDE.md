# CLAUDE.md - AI Assistant Development Guide

> **Purpose**: This document provides AI assistants with comprehensive context about the Theoria codebase structure, development workflows, architecture patterns, and conventions to follow when contributing to the project.

**Last Updated**: 2025-01-15
**Project Version**: 0.0.0
**Status**: Active Development

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Quick Reference](#quick-reference)
3. [Architecture & Design Principles](#architecture--design-principles)
4. [Codebase Structure](#codebase-structure)
5. [Tech Stack & Dependencies](#tech-stack--dependencies)
6. [Development Workflows](#development-workflows)
7. [Code Conventions & Patterns](#code-conventions--patterns)
8. [Testing Strategy](#testing-strategy)
9. [API & Integration Patterns](#api--integration-patterns)
10. [Database & Data Layer](#database--data-layer)
11. [Security & Authentication](#security--authentication)
12. [Common Tasks & Examples](#common-tasks--examples)
13. [Troubleshooting & Debugging](#troubleshooting--debugging)
14. [Documentation Map](#documentation-map)

---

## Project Overview

**Theoria** is an evidence-first theological research platform that transforms scattered research materials into a searchable, verse-aware knowledge graph. Every automated insight traces back to canonical biblical text through deterministic retrieval and OSIS reference normalization.

### Core Mission
- **Grounded Answers**: Deterministic retrieval with citations for every verse
- **Productivity Workflows**: AI summarization with strict reference enforcement
- **Operational Confidence**: Built-in observability, testing, and performance guardrails

### Key Capabilities
- Hybrid semantic + lexical search with pgvector embeddings
- Automatic OSIS normalization and verse span aggregation
- Multi-format ingestion (PDFs, URLs, YouTube, audio transcripts)
- Modern Next.js UI with command palette (⌘K/CTRL+K)
- REST API + CLI automation hooks
- Discovery engines for pattern detection, contradictions, and research insights

---

## Quick Reference

### Essential Commands

```bash
# Environment Setup
python -m venv .venv && source .venv/bin/activate  # Unix
pip install ".[api]" ".[ml]" ".[dev]" -c constraints/prod.txt -c constraints/dev.txt

# Start Services (PowerShell)
.\start-theoria.ps1                    # Smart launcher with health monitoring
.\start-theoria.ps1 -Profile staging   # Staging profile
.\start-theoria.ps1 -UseHttps          # HTTPS with self-signed certs

# Start Services (Manual)
uvicorn theo.infrastructure.api.app.main:app --reload --host 127.0.0.1 --port 8000  # API
cd theo/services/web && npm run dev                                                  # Web UI

# Testing
task test:fast              # Fast suite (no slow/gpu/contract/pgvector)
task test:full              # Full suite including heavy tests
pytest -m "not slow"        # Skip slow tests
pytest --pgvector           # Run pgvector integration tests
npm run test:vitest         # Frontend unit tests
npm run test:e2e:smoke      # E2E smoke tests

# Quality Gates
task architecture:test      # Architecture enforcement
ruff check theo/            # Python linting
ruff format theo/           # Python formatting
mypy theo/                  # Type checking
cd theo/services/web && npm run lint  # Frontend linting

# Dependency Management
python scripts/update_constraints.py        # Regenerate lockfiles
python scripts/update_constraints.py --check  # Validate constraints

# Database
task db:start              # Start local PostgreSQL
./scripts/reset_reseed_smoke.py --log-level INFO  # Seed demo content
```

### Key URLs (Local Development)
- **Web UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/health
- **GraphQL Explorer**: http://localhost:3000/admin/graphql

### Important File Locations
- **API Entry**: `theo/infrastructure/api/app/main.py`
- **Web Entry**: `theo/services/web/app/page.tsx`
- **Environment Config**: `.env.example` → `.env`
- **Constraints**: `constraints/prod.txt`, `constraints/dev.txt`
- **Task Runner**: `Taskfile.yml`

---

## Architecture & Design Principles

### Hexagonal (Ports & Adapters) Architecture

Theoria follows strict hexagonal architecture with layer separation enforced by `import-linter`.

```
┌─────────────────────────────────────────────────────┐
│              Infrastructure Layer                   │
│  (FastAPI, GraphQL, Celery, Framework Code)         │
│         theo/infrastructure/                        │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│              Adapters Layer                         │
│  (Persistence, Events, Graph, Secrets)              │
│         theo/adapters/                              │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│              Application Layer                      │
│  (Use Cases, DTOs, Facades, Repositories)           │
│         theo/application/                           │
└───────────────────┬─────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────┐
│              Domain Layer                           │
│  (Business Logic, Domain Models, Interfaces)        │
│         theo/domain/                                │
└─────────────────────────────────────────────────────┘
```

### Layer Rules (Strictly Enforced)

1. **Domain Layer** (`theo.domain`)
   - Pure business logic, no framework dependencies
   - Contains: Value objects, entities, domain services, repository interfaces
   - Cannot import from: Application, Adapters, Infrastructure
   - Example: `theo/domain/biblical_texts.py`, `theo/domain/discoveries/`

2. **Application Layer** (`theo.application`)
   - Use cases and orchestration logic
   - Contains: DTOs (frozen dataclasses), repository abstractions, facades, ports
   - Cannot import from: Infrastructure
   - Can import from: Domain
   - Example: `theo/application/dtos/`, `theo/application/facades/`

3. **Adapters Layer** (`theo.adapters`)
   - Implements ports defined in application layer
   - Contains: SQLAlchemy repositories, mappers, event handlers, external service adapters
   - Can import from: Domain, Application
   - Example: `theo/adapters/persistence/`, `theo/adapters/research/`

4. **Infrastructure Layer** (`theo.infrastructure`)
   - Framework-specific code (FastAPI, GraphQL)
   - Contains: API routes, Celery workers, bootstrap code, dependency injection
   - Can import from: Domain, Application, Adapters
   - Example: `theo/infrastructure/api/app/routes/`, `theo/infrastructure/api/app/workers/`

### Key Design Patterns

**Repository Pattern**: Abstract data access
```python
# Interface in application layer
class DiscoveryRepository(Protocol):
    def list(self, filters: DiscoveryListFilters) -> list[DiscoveryDTO]: ...

# Implementation in adapters layer
class SQLAlchemyDiscoveryRepository(BaseRepository, DiscoveryRepository):
    def list(self, filters: DiscoveryListFilters) -> list[DiscoveryDTO]:
        # SQLAlchemy implementation
```

**DTO Pattern**: Immutable data transfer objects
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class DiscoveryDTO:
    id: int
    user_id: str
    discovery_type: str
    confidence: float
    # ... all fields immutable
```

**Discovery Engine Pattern**: All discovery engines follow consistent interface
```python
class XyzDiscoveryEngine:
    def detect(self, documents: Sequence[DocumentEmbedding]) -> list[XyzDiscovery]:
        # 1. Validate input
        # 2. Run detection algorithm
        # 3. Filter and rank by confidence
        # 4. Return top N results
```

**Mapper Pattern**: Explicit DTO ↔ Model conversion in adapters layer
```python
def discovery_to_dto(model: Discovery) -> DiscoveryDTO:
    """Convert SQLAlchemy model to DTO."""
    return DiscoveryDTO(id=model.id, user_id=model.user_id, ...)
```

### Pragmatic Clean Architecture Guidelines

While Theoria enforces strict hexagonal architecture via `import-linter`, overly rigid adherence can create "Pass-Through Hell" where simple operations require excessive DTO mapping. Follow these guidelines to balance purity with velocity:

**When to Use Full DTO Mapping**
- External API contracts that require versioning independent of domain models
- Complex mutations that aggregate data from multiple sources
- Cross-boundary operations where input/output shapes differ significantly
- Data that needs transformation or validation before persistence

**When to Allow Domain Entities Directly**
- Read-only queries returning data in its natural shape
- Internal service-to-service communication within trust boundaries
- Simple CRUD operations where DTO adds no value
- Performance-critical paths where mapping overhead is measurable

**Example: Pragmatic Read Operation**
```python
# Instead of mapping to DTO for simple reads:
@router.get("/discoveries/{id}")
def get_discovery(id: int, session: Session = Depends(get_session)):
    # OK to return domain entity for simple reads
    discovery = session.get(Discovery, id)
    if not discovery:
        raise NotFoundError(f"Discovery {id}")
    return DiscoveryResponse.model_validate(discovery)  # Pydantic handles conversion
```

**See Also**: `docs/adr/0006-local-llm-first-architecture.md` for privacy-first patterns

---

## Codebase Structure

### Top-Level Organization

```
/home/user/Theoria/
├── theo/                          # Main application code
│   ├── domain/                    # Domain layer (business logic)
│   ├── application/               # Application layer (use cases, DTOs)
│   ├── adapters/                  # Adapters (persistence, events)
│   ├── infrastructure/            # Infrastructure (API, framework code)
│   ├── services/                  # Services (web UI, CLI)
│   ├── data/                      # Data providers and research resources
│   └── commands/                  # CLI commands
├── tests/                         # Comprehensive test suite
│   ├── unit/                      # Pure unit tests
│   ├── integration/               # Integration tests
│   ├── api/                       # API endpoint tests
│   ├── domain/                    # Domain logic tests
│   ├── architecture/              # Architecture enforcement tests
│   ├── workers/                   # Celery worker tests
│   ├── perf/                      # Performance benchmarks
│   └── redteam/                   # Security tests
├── docs/                          # Documentation
│   ├── adr/                       # Architecture Decision Records
│   ├── archive/                   # Archived documentation
│   ├── planning/                  # Planning documents
│   ├── research/                  # User research
│   └── testing/                   # Testing documentation
├── scripts/                       # Utility scripts
│   ├── perf/                      # Performance profiling
│   ├── security/                  # Security validation
│   └── debug/                     # Debugging helpers
├── infra/                         # Infrastructure configuration
├── fixtures/                      # Test fixtures (HTML, PDF, YouTube)
├── data/                          # Data files (bibles, seeds, eval)
├── constraints/                   # Dependency lockfiles
├── .github/workflows/             # CI/CD pipelines
└── [Configuration files]          # pyproject.toml, Taskfile.yml, etc.
```

### Core Python Modules

**Domain Layer** (`theo/domain/`)
```
domain/
├── __init__.py
├── biblical_texts.py         # Biblical text domain models
├── documents.py               # Document domain models
├── errors.py                  # Domain error hierarchy
├── references.py              # Reference value objects
├── discoveries/               # Discovery domain logic
│   ├── engine.py              # Pattern detection
│   └── contradiction_engine.py
├── repositories/              # Repository interfaces
├── services/                  # Domain services (embeddings)
├── mappers/                   # Domain object mappers
└── research/                  # Research domain models
```

**Application Layer** (`theo/application/`)
```
application/
├── __init__.py
├── dtos/                      # Data Transfer Objects
│   ├── discovery.py
│   ├── document.py
│   ├── chat.py
│   └── ...
├── repositories/              # Repository abstractions
├── services/                  # Application services
├── facades/                   # Cross-cutting concerns
│   ├── database.py            # Database session management
│   ├── settings.py            # Configuration
│   └── runtime.py
├── ports/                     # Port interfaces
├── search/                    # Search application logic
├── research/                  # Research workflows
├── embeddings/                # Embedding services
├── observability.py           # Tracing and monitoring
├── security.py                # Security policies
└── telemetry.py               # Telemetry configuration
```

**Adapters Layer** (`theo/adapters/`)
```
adapters/
├── __init__.py
├── persistence/               # SQLAlchemy repositories
│   ├── models.py              # ORM models (66KB)
│   ├── migrations/            # Database migrations
│   ├── mappers.py             # DTO/Model mappings
│   ├── discovery_repository.py
│   ├── document_repository.py
│   └── ...
├── events/                    # Event handling
├── graph/                     # Graph adapters
├── research/                  # Research adapters
└── secrets/                   # Secret management
```

**Infrastructure Layer** (`theo/infrastructure/api/app/`)
```
infrastructure/api/app/
├── __init__.py
├── main.py                    # FastAPI application entrypoint
├── routes/                    # API route handlers
│   ├── search.py
│   ├── documents.py
│   ├── discoveries_v1.py      # Versioned routes
│   ├── ai/                    # AI workflows
│   └── export/                # Export functionality
├── graphql/                   # GraphQL schema and resolvers
├── workers/                   # Celery task definitions
├── models/                    # Pydantic API models
├── ingest/                    # Ingestion pipeline
├── retriever/                 # Retrieval logic
├── bootstrap/                 # Application initialization
├── core/                      # Core utilities and settings
├── mcp/                       # Model Context Protocol support
├── error_handlers.py          # Centralized error handling
└── versioning.py              # API versioning support
```

### Frontend Structure (`theo/services/web/`)

```
web/
├── app/                       # Next.js 16 App Router
│   ├── page.tsx               # Home page
│   ├── layout.tsx             # Root layout
│   ├── search/                # Search interface
│   ├── verse/[osis]/          # Dynamic verse pages
│   ├── research/              # Research workspace
│   ├── copilot/               # AI copilot features
│   ├── dashboard/             # User dashboard
│   ├── notebooks/[id]/        # Notebook editor
│   ├── admin/                 # Admin interface
│   │   └── graphql/           # GraphQL explorer
│   ├── api/                   # Next.js API routes
│   └── components/            # Shared components
│       ├── AppShell.tsx
│       ├── CommandPalette.tsx
│       ├── ErrorBoundary.tsx
│       └── ...
├── tests/                     # Frontend tests
│   ├── unit/                  # Jest/Vitest tests
│   └── e2e/                   # Playwright tests
├── public/                    # Static assets
├── styles/                    # Global styles
├── types/                     # TypeScript type definitions
└── package.json
```

---

## Tech Stack & Dependencies

### Backend (Python 3.11+)

**Core Framework**
- **FastAPI** 0.119+ - Modern async web framework
- **Uvicorn** 0.38+ - ASGI server with hot reload
- **SQLAlchemy** 2.0+ - ORM with 2.0 API style
- **Pydantic** 2.5+ - Data validation with Settings
- **Strawberry GraphQL** 0.220+ - GraphQL for admin interface

**Task Processing**
- **Celery** 5.5+ - Distributed task queue
- **APScheduler** 3.10+ - Task scheduling
- **Redis** - Broker/backend for Celery

**AI/ML Stack**
- **PyTorch** 2.5+ (CPU-optimized)
- **transformers** 4.30+ - HuggingFace models
- **FlagEmbedding** 1.2+ - BAAI/bge-m3 embeddings (1024 dims)
- **BERTopic** 0.15+ - Topic modeling
- **OpenAI Whisper** - Audio transcription
- **scikit-learn** 1.4+ - ML algorithms

**Document Processing**
- **pypdf** 6.1+ - PDF parsing
- **defusedxml** 0.7+ - Safe XML parsing
- **webvtt-py** 0.5+ - Subtitle parsing
- **pythonbible** 0.13+ - OSIS reference handling

**Database**
- **PostgreSQL** 16+ with **pgvector** extension
- **SQLite** for development/testing

**Security & Observability**
- **cryptography** 46.0+ - Encryption
- **PyJWT** 2.10+ - JWT authentication
- **OpenTelemetry** 1.25+ - Tracing
- **Prometheus** 0.20+ - Metrics

**Development Tools**
- **pytest** 8.3+ with extensive plugins
  - pytest-cov, pytest-xdist, pytest-timeout
  - pytest-split (CI parallelization)
  - hypothesis (property-based testing)
  - testcontainers 4.13+ (integration tests)
- **Ruff** 0.14.0 - Linting + formatting
- **mypy** 1.18+ - Type checking
- **import-linter** 2.0+ - Architecture enforcement

### Frontend (TypeScript/JavaScript)

**Core Framework**
- **Next.js** 16.0.1 - React framework (App Router)
- **React** 19.2.0 - UI library
- **TypeScript** 5.9.3 - Type safety

**UI Libraries**
- **Radix UI** - Accessible primitives (dialog, dropdown, toast, tooltip)
- **Lucide React** - Icon library
- **cmdk** - Command palette (⌘K/CTRL+K)
- **D3.js** 7.9 - Data visualizations
- **TanStack Virtual** - List virtualization

**Testing**
- **Jest** 30.2.0 with Testing Library
- **Vitest** 4.0.3 with V8 coverage
- **Playwright** 1.56.1 - E2E tests
- **MSW** 2.6.8 - API mocking
- **Percy** - Visual regression
- **Axe** - Accessibility testing (WCAG 2.1 AA)

**Quality Tools**
- **ESLint** 9.39+ with TypeScript plugin
- **Lighthouse CI** 0.15.1 - Performance monitoring
- **Bundle Analyzer** - Bundle size optimization

### Infrastructure

- **Docker** - Containerization with multi-stage builds
- **Docker Compose** - Local orchestration
- **go-task** - Task runner (Taskfile.yml)
- **GitHub Actions** - CI/CD with matrix builds
- **CycloneDX** - SBOM generation (Python + Node)

---

## Development Workflows

### Initial Setup

```bash
# 1. Clone and create virtual environment
git clone https://github.com/dmedlin87/theoria.git
cd theoria
python -m venv .venv
source .venv/bin/activate  # Unix
# .venv\Scripts\activate   # Windows

# 2. Install Python dependencies
pip install ".[api]" -c constraints/prod.txt
pip install ".[ml]" -c constraints/prod.txt
pip install ".[dev]" -c constraints/dev.txt

# 3. Install frontend dependencies
cd theo/services/web
npm install
cd ../..

# 4. Install Playwright browsers (optional, for E2E tests)
cd theo/services/web
npx playwright install --with-deps
cd ../..

# 5. Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Environment Configuration

**Required Variables** (`.env`):
```bash
# Database
DATABASE_URL=postgresql://theoria:theoria@localhost:5432/theoria  # or sqlite:///./theo.db

# Authentication (optional in development - key is auto-generated)
# THEO_API_KEYS='["my-api-key"]'  # Set for persistent keys

# Runtime
THEORIA_ENVIRONMENT=development
STORAGE_ROOT=./storage
REDIS_URL=redis://localhost:6379/0

# Embeddings
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
MAX_CHUNK_TOKENS=900

# Frontend (if using Next.js API routes)
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
# THEO_SEARCH_API_KEY will be printed to console on API startup
```

### Starting Services

**Option 1: Smart Launcher (Recommended)**
```powershell
# PowerShell (Windows)
.\start-theoria.ps1                    # Standard dev mode
.\start-theoria.ps1 -Profile staging   # Staging profile
.\start-theoria.ps1 -UseHttps          # HTTPS with self-signed certs
.\start-theoria.ps1 -Verbose           # Detailed logging

# Features:
# ✓ Automatic prerequisite checks
# ✓ Environment setup
# ✓ Health monitoring with auto-restart
# ✓ Graceful shutdown (Ctrl+C)
```

**Option 2: Manual Startup**
```bash
# Terminal 1: API (in development mode, API key is auto-generated)
export THEORIA_ENVIRONMENT=development
uvicorn theo.infrastructure.api.app.main:app --reload --host 127.0.0.1 --port 8000
# Copy the auto-generated API key from the console output

# Terminal 2: Web UI
cd theo/services/web
export NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
export THEO_SEARCH_API_KEY="Bearer <auto-generated-key>"  # Use key from API console
npm run dev
```

**Option 3: Docker Compose**
```bash
cd infra
docker compose up --build -d
# Web: http://localhost:3000
# API: http://localhost:8000/docs
```

### Development Loop

```bash
# 1. Create feature branch
git checkout -b feature/your-feature-name

# 2. Implement changes
# - Write tests first (TDD recommended)
# - Follow architecture layers
# - Use type hints and docstrings

# 3. Run tests locally
task test:fast                    # Quick validation
pytest tests/your_module -v      # Targeted tests
cd theo/services/web && npm run test:vitest  # Frontend tests

# 4. Run quality checks
ruff check theo/                  # Linting
ruff format theo/                 # Formatting
mypy theo/                        # Type checking
task architecture:test            # Architecture enforcement

# 5. Commit changes
git add .
git commit -m "feat: add xyz feature"

# 6. Push and create PR
git push -u origin feature/your-feature-name
```

### Dependency Management

```bash
# After editing pyproject.toml dependencies
python scripts/update_constraints.py        # Regenerate lockfiles
python scripts/update_constraints.py --check  # Validate (CI mode)

# Install updated dependencies
pip install ".[api]" ".[ml]" ".[dev]" -c constraints/prod.txt -c constraints/dev.txt

# Frontend dependencies
cd theo/services/web
npm install
npm audit fix  # Fix security vulnerabilities
```

### Database Management

```bash
# Start local PostgreSQL (using task)
task db:start

# Or manually with Docker
docker run --rm --name theoria-db \
  -e POSTGRES_PASSWORD=theoria \
  -e POSTGRES_USER=theoria \
  -e POSTGRES_DB=theoria \
  -p 5432:5432 ankane/pgvector:0.5.2

# Run migrations
python -m theo.infrastructure.api.app.db.run_sql_migrations

# Seed demo data
./scripts/reset_reseed_smoke.py --log-level INFO
```

---

## Code Conventions & Patterns

### Python Code Style

**Type Hints** (Required for all functions)
```python
from __future__ import annotations  # Enable forward references

from typing import Sequence
from datetime import datetime, UTC

def process_documents(
    documents: Sequence[DocumentDTO],
    limit: int | None = None,
    *,
    user_id: str,
) -> list[DiscoveryDTO]:
    """Process documents and return discoveries.

    Args:
        documents: Documents to process
        limit: Optional limit on results
        user_id: User identifier (keyword-only)

    Returns:
        List of discoveries sorted by confidence

    Raises:
        ValidationError: If documents are invalid
        NotFoundError: If user not found
    """
    ...
```

**Imports Organization**
```python
# 1. Future imports
from __future__ import annotations

# 2. Standard library
import logging
from datetime import UTC, datetime
from typing import Sequence

# 3. Third-party
import numpy as np
from sqlalchemy import select
from pydantic import BaseModel

# 4. Local imports (absolute)
from theo.domain.discoveries import DiscoveryType
from theo.domain.errors import NotFoundError
from theo.application.dtos import DiscoveryDTO

# 5. Relative imports (within same package)
from ..models import Discovery
from .base import BaseRepository
```

**Docstrings** (Google style)
```python
def function(param: str, optional: int = 0) -> bool:
    """Short one-line description.

    Longer description providing more context about what this
    function does and when to use it.

    Args:
        param: Description of required parameter
        optional: Description of optional parameter (default: 0)

    Returns:
        True if successful, False otherwise

    Raises:
        ValueError: When param is invalid
        RuntimeError: When operation fails

    Example:
        >>> function("test", 42)
        True
    """
```

**Error Handling**
```python
# Use specific exceptions from domain.errors
from theo.domain.errors import (
    ValidationError,
    NotFoundError,
    AuthorizationError,
    RateLimitError,
)

try:
    result = risky_operation()
except ValueError as exc:
    logger.exception("Failed to process: %s", exc)
    raise ValidationError("Invalid input provided") from exc
except KeyError as exc:
    raise NotFoundError(f"Resource not found: {exc}") from exc
```

**Frozen Dataclasses for DTOs**
```python
from dataclasses import dataclass

@dataclass(frozen=True)  # Immutable
class DiscoveryDTO:
    """Discovery data transfer object."""
    id: int
    user_id: str
    discovery_type: str
    title: str
    description: str | None
    confidence: float  # 0.0 - 1.0
    metadata: dict[str, object]  # JSON-serializable
```

### TypeScript/React Code Style

**Component Structure**
```tsx
// ComponentName.tsx
import { useState, useEffect } from 'react';
import styles from './ComponentName.module.css';

interface ComponentNameProps {
  /** Required prop with documentation */
  requiredProp: string;
  /** Optional prop with default */
  optionalProp?: number;
  /** Event handler */
  onAction?: (value: string) => void;
}

/**
 * ComponentName provides XYZ functionality.
 *
 * @example
 * <ComponentName requiredProp="value" onAction={handleAction} />
 */
export function ComponentName({
  requiredProp,
  optionalProp = 0,
  onAction,
}: ComponentNameProps) {
  const [state, setState] = useState<string>('');

  useEffect(() => {
    // Side effects
  }, [requiredProp]);

  const handleClick = () => {
    onAction?.(state);
  };

  return (
    <div className={styles.container}>
      <button onClick={handleClick} className={styles.button}>
        {requiredProp}
      </button>
    </div>
  );
}
```

**API Calls**
```tsx
// Use fetch with proper error handling
async function fetchDiscoveries(userId: string): Promise<Discovery[]> {
  try {
    const response = await fetch(`/api/discoveries?user_id=${userId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.THEO_SEARCH_API_KEY}`,
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Failed to fetch discoveries:', error);
    throw error;
  }
}
```

**CSS Modules**
```css
/* ComponentName.module.css */
.container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
}

.button {
  padding: var(--spacing-2) var(--spacing-4);
  background-color: var(--color-primary);
  color: var(--color-text-on-primary);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
}

.button:hover {
  background-color: var(--color-primary-hover);
}
```

---

## Testing Strategy

### Test Organization

```
tests/
├── unit/              # Pure unit tests (fast, no I/O)
├── integration/       # Integration tests (DB, external services)
├── api/               # API endpoint tests
├── domain/            # Domain logic tests
├── application/       # Application layer tests
├── adapters/          # Adapter tests
├── architecture/      # Architecture enforcement
├── contracts/         # Contract tests (Schemathesis)
├── perf/              # Performance benchmarks
├── e2e/               # End-to-end tests (if Python)
├── redteam/           # Security tests (OWASP LLM)
├── workers/           # Celery worker tests
├── fixtures/          # Shared test fixtures
├── factories/         # Test data factories
└── conftest.py        # Root pytest configuration
```

### Pytest Markers

Use markers to categorize tests:

```python
import pytest

@pytest.mark.slow
def test_expensive_operation():
    """Long-running test (opt-in)."""
    pass

@pytest.mark.pgvector
def test_vector_search(pgvector_session):
    """Requires pgvector/Postgres testcontainer."""
    pass

@pytest.mark.celery
def test_async_task(celery_worker):
    """Celery worker integration test."""
    pass

@pytest.mark.redteam
def test_injection_protection():
    """OWASP LLM red-team test."""
    pass
```

**Available Markers**:
- `slow` - Long-running tests (opt-in)
- `pgvector` - Requires pgvector/Postgres testcontainer
- `celery` - Celery worker integration
- `schema` - Database schema migrations
- `contract` - Contract-level compatibility
- `gpu` - GPU runtime required
- `e2e` - End-to-end/system tests
- `db` - Database-hitting tests
- `network` - Tests that reach network
- `perf` - Performance benchmarks
- `flaky` - Known-intermittent tests
- `redteam` - Security tests

### Test Execution

```bash
# Fast suite (default for local dev)
task test:fast
pytest -m "not (slow or gpu or contract or pgvector)"

# Parallel execution
task test:parallel
pytest -n=auto --dist=worksteal

# Full suite (CI)
task test:full
pytest --schema --pgvector --contract

# Specific markers
pytest -m "pgvector and not slow"
pytest --schema -m contract

# With coverage
pytest --cov=theo --cov-report=html --cov-report=xml
# Open htmlcov/index.html

# Frontend tests
cd theo/services/web
npm run test:vitest              # Unit tests with coverage
npm run test:e2e:smoke           # E2E smoke tests
npm run test:e2e:full            # Full E2E suite
```

### Writing Good Tests

**Unit Test Example**
```python
# tests/domain/discoveries/test_pattern_engine.py

import pytest
from theo.domain.discoveries import PatternDiscoveryEngine, DocumentEmbedding

@pytest.fixture
def sample_documents():
    """Fixture providing test documents."""
    return [
        DocumentEmbedding(
            document_id="doc1",
            title="Test Document",
            abstract="Test abstract",
            topics=["theology", "exegesis"],
            verse_ids=[43001001, 43001002],  # John 1:1-2
            embedding=[0.1] * 1024,
            metadata={"source": "test"},
        ),
    ]

def test_engine_initialization():
    """Test engine initializes with default parameters."""
    engine = PatternDiscoveryEngine()
    assert engine.min_confidence == 0.7
    assert engine.max_results == 20

def test_detect_with_valid_input(sample_documents):
    """Test pattern detection with valid documents."""
    engine = PatternDiscoveryEngine()
    discoveries = engine.detect(sample_documents)

    assert isinstance(discoveries, list)
    for discovery in discoveries:
        assert 0.0 <= discovery.confidence <= 1.0
        assert discovery.title
        assert discovery.description

def test_detect_with_insufficient_documents():
    """Test detection returns empty list with too few documents."""
    engine = PatternDiscoveryEngine()
    discoveries = engine.detect([])
    assert discoveries == []

@pytest.mark.slow
def test_detect_large_corpus(large_corpus_fixture):
    """Integration test with large document set."""
    engine = PatternDiscoveryEngine()
    discoveries = engine.detect(large_corpus_fixture)
    assert len(discoveries) > 0
```

**Integration Test Example**
```python
# tests/integration/test_discovery_service.py

import pytest
from sqlalchemy.orm import Session
from theo.adapters.persistence import SQLAlchemyDiscoveryRepository
from theo.infrastructure.api.app.discoveries.service import DiscoveryService

@pytest.mark.db
def test_refresh_discoveries_end_to_end(session: Session, user_id: str):
    """Test full discovery refresh workflow."""
    # Setup: Create test documents
    create_test_documents(session, user_id, count=10)

    # Execute: Refresh discoveries
    repo = SQLAlchemyDiscoveryRepository(session)
    service = DiscoveryService(repo)
    discoveries = service.refresh_user_discoveries(user_id)

    # Assert: Verify results
    assert len(discoveries) > 0
    assert all(d.user_id == user_id for d in discoveries)

    # Verify database state
    from theo.adapters.persistence.models import Discovery
    db_discoveries = session.query(Discovery).filter_by(user_id=user_id).all()
    assert len(db_discoveries) == len(discoveries)
```

**Frontend Test Example**
```tsx
// tests/unit/ComponentName.test.tsx

import { render, screen, fireEvent } from '@testing-library/react';
import { ComponentName } from '@/app/components/ComponentName';

describe('ComponentName', () => {
  it('renders with required props', () => {
    render(<ComponentName requiredProp="test" />);
    expect(screen.getByText('test')).toBeInTheDocument();
  });

  it('calls onAction when button clicked', () => {
    const handleAction = jest.fn();
    render(<ComponentName requiredProp="test" onAction={handleAction} />);

    fireEvent.click(screen.getByRole('button'));
    expect(handleAction).toHaveBeenCalledWith(expect.any(String));
  });

  it('applies custom className', () => {
    const { container } = render(<ComponentName requiredProp="test" />);
    expect(container.firstChild).toHaveClass('container');
  });
});
```

---

## API & Integration Patterns

### FastAPI Route Pattern

```python
# theo/infrastructure/api/app/routes/discoveries_v1.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session
from theo.application.dtos import DiscoveryDTO, DiscoveryListFilters
from theo.adapters.persistence import SQLAlchemyDiscoveryRepository
from ..security import Principal, require_principal
from ..models.discovery import DiscoveryResponse, DiscoveryListResponse

router = APIRouter(prefix="/api/v1/discoveries", tags=["discoveries"])

@router.get("/", response_model=DiscoveryListResponse)
def list_discoveries(
    discovery_type: str | None = Query(None, description="Filter by type"),
    viewed: bool | None = Query(None, description="Filter by viewed status"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
) -> DiscoveryListResponse:
    """List user's discoveries with optional filtering.

    Returns discoveries sorted by relevance score (descending).
    Requires authentication.
    """
    user_id = principal["subject"]

    # Build filters
    filters = DiscoveryListFilters(
        user_id=user_id,
        discovery_type=discovery_type,
        viewed=viewed,
        limit=limit,
    )

    # Query via repository
    repo = SQLAlchemyDiscoveryRepository(session)
    discoveries = repo.list(filters)

    # Convert to response models
    return DiscoveryListResponse(
        discoveries=[DiscoveryResponse.model_validate(d) for d in discoveries],
        total=len(discoveries),
    )

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_discovery(
    request: CreateDiscoveryRequest,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
) -> DiscoveryResponse:
    """Create a new discovery manually."""
    user_id = principal["subject"]

    # Validate and create via repository
    repo = SQLAlchemyDiscoveryRepository(session)
    discovery = repo.create(user_id, request)

    return DiscoveryResponse.model_validate(discovery)
```

### Pydantic Models

```python
# theo/infrastructure/api/app/models/discovery.py

from pydantic import BaseModel, Field
from datetime import datetime

class DiscoveryResponse(BaseModel):
    """Discovery API response model."""
    id: int
    user_id: str
    discovery_type: str
    title: str
    description: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    relevance_score: float = Field(ge=0.0, le=1.0)
    viewed: bool
    created_at: datetime
    metadata: dict[str, object]

    model_config = {"from_attributes": True}  # Enable ORM mode

class DiscoveryListResponse(BaseModel):
    """List response wrapper."""
    discoveries: list[DiscoveryResponse]
    total: int

class CreateDiscoveryRequest(BaseModel):
    """Request to create discovery."""
    discovery_type: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    confidence: float = Field(0.8, ge=0.0, le=1.0)
```

### Error Handling

```python
# Error handlers are centralized in error_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse
from theo.domain.errors import (
    NotFoundError,
    ValidationError,
    AuthorizationError,
)

@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "message": str(exc),
            "trace_id": request.state.trace_id,
        },
    )

@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": str(exc),
            "trace_id": request.state.trace_id,
        },
    )
```

### Dependency Injection

```python
# Common dependencies in theo/application/facades/

from sqlalchemy.orm import Session
from theo.application.facades.database import get_session
from theo.infrastructure.api.app.security import require_principal

# Usage in routes
@router.get("/")
def endpoint(
    principal: Principal = Depends(require_principal),  # Authentication
    session: Session = Depends(get_session),            # Database session
):
    user_id = principal["subject"]
    # ... use session for queries
```

---

## Database & Data Layer

### SQLAlchemy Models

```python
# theo/adapters/persistence/models.py

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, UTC

Base = declarative_base()

class Discovery(Base):
    """Discovery ORM model."""
    __tablename__ = "discoveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    discovery_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    relevance_score = Column(Float, nullable=False, default=0.0)
    viewed = Column(Boolean, nullable=False, default=False, index=True)
    user_reaction = Column(String, nullable=True)  # thumbs_up, thumbs_down, etc.
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    meta = Column(JSONB, nullable=True)  # Type-specific metadata

    def __repr__(self):
        return f"<Discovery(id={self.id}, type={self.discovery_type}, title={self.title!r})>"
```

### Repository Implementation

```python
# theo/adapters/persistence/discovery_repository.py

from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from theo.application.repositories import DiscoveryRepository
from theo.application.dtos import DiscoveryDTO, DiscoveryListFilters
from .models import Discovery
from .mappers import discovery_to_dto, dto_to_discovery
from .base import BaseRepository

class SQLAlchemyDiscoveryRepository(BaseRepository, DiscoveryRepository):
    """SQLAlchemy implementation of DiscoveryRepository."""

    def __init__(self, session: Session):
        super().__init__(session)

    def list(self, filters: DiscoveryListFilters) -> list[DiscoveryDTO]:
        """List discoveries with optional filters."""
        stmt = select(Discovery).where(Discovery.user_id == filters.user_id)

        # Apply optional filters
        if filters.discovery_type:
            stmt = stmt.where(Discovery.discovery_type == filters.discovery_type)
        if filters.viewed is not None:
            stmt = stmt.where(Discovery.viewed == filters.viewed)

        # Sort by relevance
        stmt = stmt.order_by(Discovery.relevance_score.desc(), Discovery.created_at.desc())

        # Apply limit
        if filters.limit:
            stmt = stmt.limit(filters.limit)

        # Execute and map to DTOs
        results = self.session.scalars(stmt).all()
        return [discovery_to_dto(r) for r in results]

    def get_by_id(self, discovery_id: int) -> DiscoveryDTO | None:
        """Get discovery by ID."""
        stmt = select(Discovery).where(Discovery.id == discovery_id)
        result = self.session.scalar(stmt)
        return discovery_to_dto(result) if result else None

    def delete_by_type(self, user_id: str, discovery_type: str) -> int:
        """Delete all discoveries of a type for a user."""
        stmt = delete(Discovery).where(
            Discovery.user_id == user_id,
            Discovery.discovery_type == discovery_type,
        )
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount
```

### Mappers

```python
# theo/adapters/persistence/mappers.py

from theo.application.dtos import DiscoveryDTO
from .models import Discovery

def discovery_to_dto(model: Discovery) -> DiscoveryDTO:
    """Convert SQLAlchemy model to DTO."""
    return DiscoveryDTO(
        id=model.id,
        user_id=model.user_id,
        discovery_type=model.discovery_type,
        title=model.title,
        description=model.description,
        confidence=model.confidence,
        relevance_score=model.relevance_score,
        viewed=model.viewed,
        user_reaction=model.user_reaction,
        created_at=model.created_at,
        metadata=model.meta or {},
    )

def dto_to_discovery(dto: DiscoveryDTO) -> Discovery:
    """Convert DTO to SQLAlchemy model."""
    return Discovery(
        id=dto.id,
        user_id=dto.user_id,
        discovery_type=dto.discovery_type,
        title=dto.title,
        description=dto.description,
        confidence=dto.confidence,
        relevance_score=dto.relevance_score,
        viewed=dto.viewed,
        user_reaction=dto.user_reaction,
        created_at=dto.created_at,
        meta=dict(dto.metadata),
    )
```

### Database Queries (SQLAlchemy 2.0 Style)

```python
from sqlalchemy import select, delete, update

# SELECT
stmt = select(Discovery).where(
    Discovery.user_id == user_id,
    Discovery.viewed == False,
).order_by(Discovery.created_at.desc())
results = session.scalars(stmt).all()

# SELECT with JOIN
from sqlalchemy.orm import joinedload
stmt = select(Discovery).options(
    joinedload(Discovery.related_entity)
).where(Discovery.id == discovery_id)
result = session.scalar(stmt)

# DELETE
stmt = delete(Discovery).where(
    Discovery.user_id == user_id,
    Discovery.discovery_type == "pattern",
)
session.execute(stmt)
session.commit()

# UPDATE
stmt = update(Discovery).where(
    Discovery.id == discovery_id
).values(viewed=True)
session.execute(stmt)
session.commit()

# INSERT
new_discovery = Discovery(
    user_id=user_id,
    discovery_type="pattern",
    title="New Discovery",
    confidence=0.85,
    created_at=datetime.now(UTC),
)
session.add(new_discovery)
session.commit()
session.refresh(new_discovery)  # Get auto-generated fields
```

---

## Security & Authentication

### Authentication Strategies

**Auto-Generated Development Key** (Default for development)

In development environments (`THEORIA_ENVIRONMENT=development`), when no API keys are configured, the API automatically generates an ephemeral key and prints it to the console. Simply start the API and copy the key from the output.

**API Key Authentication** (Persistent keys)
```bash
# .env
THEO_API_KEYS='["my-api-key", "another-key"]'
```

```python
# Usage in API clients
headers = {
    "Authorization": "Bearer my-api-key",
    # OR
    "X-API-Key": "my-api-key",
}
```

**JWT Authentication** (Production)
```bash
# .env
THEO_AUTH_JWT_SECRET=your-secret-key-here
THEO_AUTH_JWT_AUDIENCE=theoria-api
THEO_AUTH_JWT_ISSUER=theoria-auth
```

### Security Headers

```python
# Automatically applied by middleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Principal Access

```python
from theo.infrastructure.api.app.security import Principal, require_principal

@router.get("/")
def endpoint(principal: Principal = Depends(require_principal)):
    user_id = principal["subject"]
    # User is authenticated
    # principal contains: {"subject": "user-id", ...}
```

### Security Best Practices

1. **Never commit secrets** - Use `.env` files (gitignored)
2. **Validate all inputs** - Use Pydantic models
3. **Parameterize SQL queries** - SQLAlchemy handles this
4. **Escape user content** - React handles XSS automatically
5. **Rate limiting** - Implemented via `RateLimitError`
6. **HTTPS in production** - Use `start-theoria.ps1 -UseHttps` for local testing

---

## Common Tasks & Examples

### Adding a New Discovery Engine

```python
# 1. Create domain model (theo/domain/discoveries/gap_discovery.py)
from dataclasses import dataclass

@dataclass(frozen=True)
class GapDiscovery:
    """Research gap discovery."""
    title: str
    description: str
    confidence: float
    relevance_score: float
    missing_topics: list[str]
    metadata: dict[str, object]

# 2. Create engine (theo/domain/discoveries/gap_engine.py)
from typing import Sequence
from ..documents import DocumentEmbedding

class GapDiscoveryEngine:
    """Detects research gaps in user's corpus."""

    def __init__(self, *, min_confidence: float = 0.7):
        self.min_confidence = min_confidence

    def detect(self, documents: Sequence[DocumentEmbedding]) -> list[GapDiscovery]:
        """Detect gaps in research coverage."""
        if len(documents) < 10:
            return []

        # Analysis logic here
        gaps = self._analyze_coverage(documents)

        # Filter by confidence
        filtered = [g for g in gaps if g.confidence >= self.min_confidence]

        # Sort by relevance
        filtered.sort(key=lambda x: x.relevance_score, reverse=True)

        return filtered[:20]  # Top 20

# 3. Integrate into service (theo/infrastructure/api/app/discoveries/service.py)
def refresh_user_discoveries(self, user_id: str) -> list[Discovery]:
    documents = self._load_document_embeddings(user_id)

    # Run all engines
    pattern_discoveries = self.pattern_engine.detect(documents)
    contradiction_discoveries = self.contradiction_engine.detect(documents)
    gap_discoveries = self.gap_engine.detect(documents)  # NEW

    # Delete old discoveries
    self.session.execute(
        delete(Discovery).where(
            Discovery.user_id == user_id,
            Discovery.discovery_type.in_([
                "pattern",
                "contradiction",
                "gap",  # NEW
            ])
        )
    )

    # Persist all
    all_discoveries = (
        pattern_discoveries +
        contradiction_discoveries +
        gap_discoveries  # NEW
    )

    for discovery in all_discoveries:
        record = Discovery(
            user_id=user_id,
            discovery_type=discovery.type,
            title=discovery.title,
            description=discovery.description,
            confidence=float(discovery.confidence),
            relevance_score=float(discovery.relevance_score),
            meta=dict(discovery.metadata),
            created_at=datetime.now(UTC),
        )
        self.session.add(record)

    self.session.commit()
    return all_discoveries

# 4. Add tests (tests/domain/discoveries/test_gap_engine.py)
import pytest
from theo.domain.discoveries import GapDiscoveryEngine

def test_gap_detection(sample_documents):
    engine = GapDiscoveryEngine()
    gaps = engine.detect(sample_documents)

    assert isinstance(gaps, list)
    for gap in gaps:
        assert 0.0 <= gap.confidence <= 1.0
        assert gap.missing_topics
```

### Adding a New API Endpoint

```python
# 1. Create Pydantic models (theo/infrastructure/api/app/models/xyz.py)
from pydantic import BaseModel, Field

class XyzRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None

class XyzResponse(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: str

    model_config = {"from_attributes": True}

# 2. Create route (theo/infrastructure/api/app/routes/xyz.py)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from theo.application.facades.database import get_session
from ..security import Principal, require_principal
from ..models.xyz import XyzRequest, XyzResponse

router = APIRouter(prefix="/api/v1/xyz", tags=["xyz"])

@router.post("/", status_code=201)
def create_xyz(
    request: XyzRequest,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
) -> XyzResponse:
    """Create new XYZ resource."""
    user_id = principal["subject"]

    # Business logic
    xyz = create_xyz_resource(session, user_id, request)

    return XyzResponse.model_validate(xyz)

# 3. Register router (theo/infrastructure/api/app/main.py)
from .routes import xyz

app.include_router(xyz.router)

# 4. Add tests (tests/api/test_xyz.py)
def test_create_xyz(client, auth_headers):
    response = client.post(
        "/api/v1/xyz/",
        json={"name": "Test"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test"
```

### Adding a Frontend Component

```tsx
// 1. Create component (theo/services/web/app/components/XyzWidget.tsx)
import { useState } from 'react';
import styles from './XyzWidget.module.css';

interface XyzWidgetProps {
  initialValue: string;
  onSave: (value: string) => Promise<void>;
}

export function XyzWidget({ initialValue, onSave }: XyzWidgetProps) {
  const [value, setValue] = useState(initialValue);
  const [isLoading, setIsLoading] = useState(false);

  const handleSave = async () => {
    setIsLoading(true);
    try {
      await onSave(value);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className={styles.input}
      />
      <button
        onClick={handleSave}
        disabled={isLoading}
        className={styles.button}
      >
        {isLoading ? 'Saving...' : 'Save'}
      </button>
    </div>
  );
}

// 2. Create styles (theo/services/web/app/components/XyzWidget.module.css)
.container {
  display: flex;
  gap: var(--spacing-2);
}

.input {
  flex: 1;
  padding: var(--spacing-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.button {
  padding: var(--spacing-2) var(--spacing-4);
  background-color: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

// 3. Add tests (theo/services/web/tests/unit/XyzWidget.test.tsx)
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { XyzWidget } from '@/app/components/XyzWidget';

describe('XyzWidget', () => {
  it('saves value when button clicked', async () => {
    const handleSave = jest.fn().mockResolvedValue(undefined);
    render(<XyzWidget initialValue="test" onSave={handleSave} />);

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'new value' } });

    const button = screen.getByRole('button', { name: /save/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(handleSave).toHaveBeenCalledWith('new value');
    });
  });
});
```

---

## Troubleshooting & Debugging

### Common Issues

**Issue: Port already in use**
```bash
# Find process using port
lsof -i :8000  # Unix
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # Unix
taskkill /PID <PID> /F  # Windows

# Or use custom ports
.\start-theoria.ps1 -ApiPort 8010 -WebPort 3100
```

**Issue: Database connection errors**
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Start PostgreSQL
task db:start

# Check DATABASE_URL in .env
echo $DATABASE_URL  # Unix
echo %DATABASE_URL%  # Windows
```

**Issue: Import errors in tests**
```bash
# Reinstall in editable mode
pip install -e ".[api]" ".[ml]" ".[dev]" -c constraints/prod.txt -c constraints/dev.txt

# Validate environment
python validate_test_env.py
```

**Issue: Node modules missing**
```bash
cd theo/services/web
rm -rf node_modules package-lock.json
npm install
```

**Issue: ML model download failures**
```bash
# Check internet connection
# Ensure disk space (models can be several GB)
pip install ".[ml]" -c constraints/prod.txt --verbose

# For offline environments, cache models first:
# See docs/INDEX.md for offline cache instructions
```

### Debugging Tips

**1. Enable Debug Logging**
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or in .env
LOG_LEVEL=DEBUG
```

**2. Use IPython for Interactive Debugging**
```python
# Add breakpoint
import IPython; IPython.embed()

# Inspect variables, test code interactively
```

**3. Check Database State**
```bash
# Connect to database
psql $DATABASE_URL

# Query discoveries
SELECT id, discovery_type, title, confidence
FROM discoveries
WHERE user_id = 'test-user'
ORDER BY created_at DESC;

# Check migrations
SELECT * FROM alembic_version;
```

**4. Inspect API Requests**
```bash
# Use curl with verbose output
curl -v http://localhost:8000/api/v1/discoveries \
  -H "Authorization: Bearer local-dev-key"

# Or use httpie for better formatting
http GET localhost:8000/api/v1/discoveries \
  Authorization:"Bearer local-dev-key"
```

**5. Frontend Debugging**
```tsx
// Use React DevTools browser extension
console.log('Component state:', state);
console.table(data);  // Pretty-print arrays/objects

// Network tab in browser DevTools
// Check API requests/responses
// Look for CORS errors
```

**6. Profile Performance**
```bash
# Profile test suite
python scripts/perf/profile_marker_suites.py

# Profile specific test
pytest tests/api/test_search.py -v --profile

# Check slow tests
python scripts/perf/slow_test_baseline.py
```

**7. Check Architecture Violations**
```bash
# Validate layer boundaries
task architecture:test
lint-imports

# Check import graph
python scripts/perf/generate_dependency_graph.py
```

---

## Documentation Map

### Essential Documents (Start Here)

| Document | Purpose |
|----------|---------|
| **README.md** | Project overview, quick start, capabilities |
| **START_HERE.md** | Getting started guide with launcher |
| **CLAUDE.md** | This file - AI assistant guide |
| **AGENT_CONTEXT.md** | Current architecture and priorities |
| **CONTRIBUTING.md** | Development workflow and testing |

### Architecture & Design

| Document | Purpose |
|----------|---------|
| **docs/architecture.md** | System architecture overview |
| **docs/API.md** | REST and agent surface contracts |
| **docs/adr/** | Architecture Decision Records |
| **IMPLEMENTATION_CONTEXT.md** | Patterns and code examples |
| **QUICK_START_ARCHITECTURE.md** | Architecture quick reference |

### Development

| Document | Purpose |
|----------|---------|
| **docs/testing.md** | Testing strategy and prerequisites |
| **docs/testing/TEST_MAP.md** | Complete test coverage map |
| **docs/document_inventory.md** | Documentation manifest |
| **docs/INDEX.md** | Master documentation index |

### Operations

| Document | Purpose |
|----------|---------|
| **DEPLOYMENT.md** | Deployment strategies and guides |
| **SECURITY.md** | Security policies and authentication |
| **THREATMODEL.md** | Security threat model |
| **docs/Repo-Health.md** | Operational dashboards and runbooks |
| **docs/performance.md** | Performance baselines and Lighthouse CI |

### Features & Workflows

| Document | Purpose |
|----------|---------|
| **QUICK_START_AGENTS.md** | Agent automation guide |
| **README_BIBLICAL_TEXTS.md** | Biblical text handling |
| **docs/OSIS.md** | OSIS reference normalization |
| **docs/Chunking.md** | Document chunking strategies |
| **docs/AGENT_CONFINEMENT.md** | Agent safety patterns |

### Planning & Research

| Document | Purpose |
|----------|---------|
| **docs/planning/SIMPLIFICATION_PLAN.md** | Current initiatives and tasks |
| **docs/research/adjacent_user_needs.md** | User research findings |
| **CHANGELOG.md** | Version history and changes |

### Archive

| Location | Content |
|----------|---------|
| **docs/archive/** | Superseded documentation |
| **docs/archive/handoffs/** | Historical handoff documents |
| **docs/archive/2025-10-26_core/** | October 2025 archive |

---

## Key Takeaways for AI Assistants

### When Working on Theoria

1. **Respect Layer Boundaries**: Never import infrastructure in domain/application layers
2. **Use DTOs**: Always use frozen dataclasses for data transfer
3. **Write Tests First**: TDD is strongly encouraged
4. **Type Everything**: Python type hints and TypeScript are required
5. **Follow Patterns**: Use existing engines/repositories as templates
6. **Check Architecture**: Run `task architecture:test` before committing
7. **Document Changes**: Update relevant .md files and docstrings
8. **Commit Incrementally**: Small, focused commits with clear messages

### Before Making Changes

1. Read relevant documentation in `docs/`
2. Check existing patterns in similar features
3. Understand the domain model
4. Plan the change across all layers
5. Write tests that will pass when implemented
6. Implement from domain → application → adapters → infrastructure

### Quality Standards

- **Test Coverage**: Aim for 80%+ coverage
- **Type Safety**: No `mypy` errors
- **Linting**: Pass `ruff check` and `ruff format`
- **Architecture**: Pass `import-linter` checks
- **Documentation**: Update docs for public APIs
- **Security**: Follow security best practices
- **Performance**: Profile slow operations

### Getting Help

1. Check **docs/INDEX.md** for navigation
2. Review **IMPLEMENTATION_CONTEXT.md** for patterns
3. Look at existing code in the same layer
4. Run tests to understand expected behavior
5. Use debug logging and IPython breakpoints
6. Ask specific questions about domain concepts

---

**Remember**: Theoria is built for precision and traceability. Every feature should maintain the commitment to verse-anchored, evidence-first theological research.

---

**Last Updated**: 2025-01-15
**Maintainer**: Theoria Development Team
**License**: See repository root
**Questions?**: See docs/ directory or open an issue
