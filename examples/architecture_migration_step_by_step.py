"""Step-by-step example of migrating to new architecture.

This file demonstrates how to gradually migrate existing code
to use DTOs, repositories, and domain errors.
"""

# ============================================================================
# STEP 1: BEFORE - Old tightly coupled approach
# ============================================================================

def old_approach_list_discoveries():
    """Old approach: Direct ORM usage in route handler."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from theo.adapters.persistence.models import Discovery
    from theo.application.facades.database import get_session

    # Route handler directly queries database
    session = next(get_session())
    try:
        stmt = select(Discovery).where(Discovery.user_id == "test")
        results = session.scalars(stmt).all()

        # Manual serialization (BAD - ORM models exposed)
        return [
            {
                "id": d.id,
                "title": d.title,
                "confidence": d.confidence,
                # ... manually copy all fields
            }
            for d in results
        ]
    finally:
        session.close()


# ============================================================================
# STEP 2: ADD DTOs - Decouple from ORM
# ============================================================================

def step2_with_dtos():
    """Improved: Use DTOs to decouple from ORM."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from theo.adapters.persistence.mappers import discovery_to_dto
    from theo.adapters.persistence.models import Discovery
    from theo.application.dtos import DiscoveryDTO
    from theo.application.facades.database import get_session

    session = next(get_session())
    try:
        stmt = select(Discovery).where(Discovery.user_id == "test")
        orm_results = session.scalars(stmt).all()

        # Convert to DTOs (BETTER - no ORM leakage)
        dto_results = [discovery_to_dto(d) for d in orm_results]
        return dto_results
    finally:
        session.close()


# ============================================================================
# STEP 3: ADD REPOSITORY - Abstract persistence
# ============================================================================

def step3_with_repository():
    """Better: Use repository pattern for abstraction."""
    from sqlalchemy.orm import Session

    from theo.adapters.persistence.discovery_repository import (
        SQLAlchemyDiscoveryRepository,
    )
    from theo.application.dtos import DiscoveryListFilters
    from theo.application.facades.database import get_session

    session = next(get_session())
    try:
        # Repository handles database details (BEST - clean abstraction)
        repo = SQLAlchemyDiscoveryRepository(session)
        filters = DiscoveryListFilters(user_id="test", viewed=False)

        # Returns DTOs, no ORM knowledge needed
        return repo.list(filters)
    finally:
        session.close()


# ============================================================================
# STEP 4: ADD DEPENDENCY INJECTION - Testable routes
# ============================================================================

def step4_dependency_injection():
    """Best: Use FastAPI dependency injection."""
    from fastapi import APIRouter, Depends
    from sqlalchemy.orm import Session

    from theo.adapters.persistence.discovery_repository import (
        SQLAlchemyDiscoveryRepository,
    )
    from theo.application.dtos import DiscoveryDTO, DiscoveryListFilters
    from theo.application.facades.database import get_session
    from theo.application.repositories import DiscoveryRepository

    router = APIRouter()

    def get_discovery_repo(session: Session = Depends(get_session)) -> DiscoveryRepository:
        """Factory for repository - easy to mock in tests."""
        return SQLAlchemyDiscoveryRepository(session)

    @router.get("/discoveries")
    def list_discoveries(
        user_id: str,
        repo: DiscoveryRepository = Depends(get_discovery_repo),
    ) -> list[DiscoveryDTO]:
        """Route handler with injected repository.

        Benefits:
        - No database code in handler
        - Easy to test (mock repository)
        - Returns type-safe DTOs
        - Works with any repository implementation
        """
        filters = DiscoveryListFilters(user_id=user_id)
        return repo.list(filters)


# ============================================================================
# STEP 5: ADD DOMAIN ERRORS - Consistent error handling
# ============================================================================

def step5_with_domain_errors():
    """Complete: Add domain errors for consistency."""
    from fastapi import APIRouter, Depends
    from sqlalchemy.orm import Session

    from theo.adapters.persistence.discovery_repository import (
        SQLAlchemyDiscoveryRepository,
    )
    from theo.application.dtos import DiscoveryDTO
    from theo.application.facades.database import get_session
    from theo.application.repositories import DiscoveryRepository
    from theo.domain.errors import NotFoundError

    router = APIRouter()

    def get_discovery_repo(session: Session = Depends(get_session)) -> DiscoveryRepository:
        return SQLAlchemyDiscoveryRepository(session)

    @router.get("/discoveries/{discovery_id}")
    def get_discovery(
        discovery_id: int,
        user_id: str,
        repo: DiscoveryRepository = Depends(get_discovery_repo),
    ) -> DiscoveryDTO:
        """Route with consistent error handling.

        Domain errors are automatically converted to HTTP responses:
        - NotFoundError → 404 with structured JSON
        - ValidationError → 422 with field details
        - etc.
        """
        discovery = repo.get_by_id(discovery_id, user_id)

        if discovery is None:
            # Raises NotFoundError which middleware converts to HTTP 404
            raise NotFoundError("Discovery", discovery_id)

        return discovery


# ============================================================================
# STEP 6: ADD USE CASE - Complex orchestration
# ============================================================================

def step6_with_use_case():
    """Advanced: Use case for complex operations."""
    from datetime import UTC, datetime

    from theo.application.dtos import DiscoveryDTO
    from theo.application.repositories import (
        DiscoveryRepository,
        DocumentRepository,
    )
    from theo.domain.discoveries import PatternDiscoveryEngine

    class RefreshDiscoveriesUseCase:
        """Orchestrates discovery refresh process.

        Benefits:
        - Testable business logic
        - Coordinates multiple repositories
        - Maintains transaction boundaries
        - Reusable across different entry points
        """

        def __init__(self, discovery_repo: DiscoveryRepository):
            self.discovery_repo = discovery_repo
            self.pattern_engine = PatternDiscoveryEngine()

        def execute(self, user_id: str, document_repo: DocumentRepository):
            """Execute discovery refresh."""
            documents = document_repo.list_with_embeddings(user_id)

            # Run domain logic
            patterns, snapshot = self.pattern_engine.detect(documents)

            # Clear old discoveries
            self.discovery_repo.delete_by_types(user_id, ["pattern"])

            # Persist new discoveries
            discoveries = []
            for pattern in patterns:
                dto = DiscoveryDTO(
                    id=0,
                    user_id=user_id,
                    discovery_type="pattern",
                    title=pattern.title,
                    description=pattern.description,
                    confidence=float(pattern.confidence),
                    relevance_score=float(pattern.relevance_score),
                    viewed=False,
                    user_reaction=None,
                    created_at=datetime.now(UTC),
                    metadata=dict(pattern.metadata),
                )
                created = self.discovery_repo.create(dto)
                discoveries.append(created)

            return discoveries


# ============================================================================
# TESTING COMPARISON
# ============================================================================

def test_old_approach():
    """Old approach: Requires database."""
    # Must setup database, create test data, etc.
    # Slow and brittle
    pass


def test_new_approach():
    """New approach: Mock repository."""
    from unittest.mock import Mock

    from theo.application.dtos import DiscoveryDTO, DiscoveryListFilters

    # Create mock repository
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

    # Test with mock (FAST - no database)
    filters = DiscoveryListFilters(user_id="test")
    results = mock_repo.list(filters)

    assert len(results) == 1
    assert results[0].title == "Test"
    # Verify mock was called correctly
    mock_repo.list.assert_called_once()


# ============================================================================
# MIGRATION CHECKLIST
# ============================================================================

MIGRATION_STEPS = """
Step-by-Step Migration Guide:

1. ✅ Create DTOs for your domain
   - File: theo/application/dtos/your_domain.py
   - Use frozen dataclasses
   - Add type hints

2. ✅ Create mappers
   - File: theo/adapters/persistence/mappers.py
   - Implement model_to_dto() and dto_to_model()

3. ✅ Create repository interface
   - File: theo/application/repositories/your_repository.py
   - Define abstract methods using DTOs

4. ✅ Implement repository
   - File: theo/adapters/persistence/your_repository.py
   - Use SQLAlchemy + mappers

5. ✅ Update routes
   - Replace direct ORM imports with DTOs
   - Inject repository via Depends()
   - Use domain errors

6. ✅ Add tests
   - Unit tests with mock repository
   - Integration tests with real database
   - Architecture tests for boundaries

7. ✅ Add to architecture tests
   - Update test_dto_boundaries.py
   - Verify no ORM imports in service layer
"""


if __name__ == "__main__":
    print(MIGRATION_STEPS)
    print("\n✅ All architectural improvements are backward compatible!")
    print("✅ Migrate incrementally at your own pace")
    print("✅ New code uses new patterns, old code continues working")
