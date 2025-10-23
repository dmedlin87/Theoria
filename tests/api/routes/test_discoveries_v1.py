"""Integration tests for v1 discovery routes using new architecture.

These tests demonstrate how the new patterns improve testability by:
- Using repository abstractions
- Mocking at the repository layer instead of database
- Testing with DTOs instead of ORM models
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from theo.application.dtos import DiscoveryDTO, DiscoveryListFilters
from theo.application.repositories import DiscoveryRepository
from theo.domain.errors import NotFoundError
from theo.services.api.app.main import app


@pytest.fixture
def mock_discovery_repo():
    """Mock discovery repository for testing."""
    return Mock(spec=DiscoveryRepository)


@pytest.fixture
def sample_discovery_dto():
    """Sample discovery DTO for testing."""
    return DiscoveryDTO(
        id=1,
        user_id="test_user",
        discovery_type="pattern",
        title="Test Pattern Discovery",
        description="A test pattern was found",
        confidence=0.85,
        relevance_score=0.75,
        viewed=False,
        user_reaction=None,
        created_at=datetime.now(UTC),
        metadata={"test": "data"},
    )


class TestDiscoveriesV1Routes:
    """Test v1 discovery routes with repository pattern."""

    def test_list_discoveries_success(self, mock_discovery_repo, sample_discovery_dto):
        """List discoveries returns DTOs from repository."""
        # Setup mock
        mock_discovery_repo.list.return_value = [sample_discovery_dto]

        # Override dependency
        from theo.services.api.app.routes import discoveries_v1
        app.dependency_overrides[discoveries_v1.get_discovery_repository] = (
            lambda: mock_discovery_repo
        )

        try:
            client = TestClient(app)
            response = client.get("/discoveries?user_id=test_user")

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["title"] == "Test Pattern Discovery"
            assert data[0]["confidence"] == 0.85

            # Verify repository was called correctly
            mock_discovery_repo.list.assert_called_once()
            call_args = mock_discovery_repo.list.call_args[0][0]
            assert isinstance(call_args, DiscoveryListFilters)
            assert call_args.user_id == "test_user"
        finally:
            app.dependency_overrides.clear()

    def test_list_discoveries_with_filters(self, mock_discovery_repo):
        """List discoveries applies all filters."""
        mock_discovery_repo.list.return_value = []

        from theo.services.api.app.routes import discoveries_v1
        app.dependency_overrides[discoveries_v1.get_discovery_repository] = (
            lambda: mock_discovery_repo
        )

        try:
            client = TestClient(app)
            response = client.get(
                "/discoveries?user_id=test_user&discovery_type=pattern&"
                "viewed=false&min_confidence=0.7&limit=10&offset=5"
            )

            assert response.status_code == 200

            # Verify filters were passed correctly
            call_args = mock_discovery_repo.list.call_args[0][0]
            assert call_args.discovery_type == "pattern"
            assert call_args.viewed is False
            assert call_args.min_confidence == 0.7
            assert call_args.limit == 10
            assert call_args.offset == 5
        finally:
            app.dependency_overrides.clear()

    def test_get_discovery_success(self, mock_discovery_repo, sample_discovery_dto):
        """Get single discovery by ID."""
        mock_discovery_repo.get_by_id.return_value = sample_discovery_dto

        from theo.services.api.app.routes import discoveries_v1
        app.dependency_overrides[discoveries_v1.get_discovery_repository] = (
            lambda: mock_discovery_repo
        )

        try:
            client = TestClient(app)
            response = client.get("/discoveries/1?user_id=test_user")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["title"] == "Test Pattern Discovery"

            mock_discovery_repo.get_by_id.assert_called_once_with(1, "test_user")
        finally:
            app.dependency_overrides.clear()

    def test_get_discovery_not_found(self, mock_discovery_repo):
        """Get discovery returns 404 for missing discovery."""
        mock_discovery_repo.get_by_id.return_value = None

        from theo.services.api.app.routes import discoveries_v1
        app.dependency_overrides[discoveries_v1.get_discovery_repository] = (
            lambda: mock_discovery_repo
        )

        try:
            client = TestClient(app)
            response = client.get("/discoveries/999?user_id=test_user")

            # Verify standardized error response
            assert response.status_code == 404
            data = response.json()
            assert "error" in data
            assert data["error"]["type"] == "NotFoundError"
            assert data["error"]["resource_type"] == "Discovery"
            assert data["error"]["resource_id"] == "999"
        finally:
            app.dependency_overrides.clear()

    def test_mark_viewed_success(self, mock_discovery_repo, sample_discovery_dto):
        """Mark discovery as viewed."""
        viewed_dto = DiscoveryDTO(
            id=sample_discovery_dto.id,
            user_id=sample_discovery_dto.user_id,
            discovery_type=sample_discovery_dto.discovery_type,
            title=sample_discovery_dto.title,
            description=sample_discovery_dto.description,
            confidence=sample_discovery_dto.confidence,
            relevance_score=sample_discovery_dto.relevance_score,
            viewed=True,  # Changed to True
            user_reaction=sample_discovery_dto.user_reaction,
            created_at=sample_discovery_dto.created_at,
            metadata=sample_discovery_dto.metadata,
        )
        mock_discovery_repo.mark_viewed.return_value = viewed_dto

        from theo.services.api.app.routes import discoveries_v1
        app.dependency_overrides[discoveries_v1.get_discovery_repository] = (
            lambda: mock_discovery_repo
        )

        try:
            client = TestClient(app)
            response = client.post("/discoveries/1/view?user_id=test_user")

            assert response.status_code == 200
            data = response.json()
            assert data["viewed"] is True

            mock_discovery_repo.mark_viewed.assert_called_once_with(1, "test_user")
        finally:
            app.dependency_overrides.clear()

    def test_mark_viewed_not_found(self, mock_discovery_repo):
        """Mark viewed returns 404 when discovery doesn't exist."""
        mock_discovery_repo.mark_viewed.side_effect = LookupError("Not found")

        from theo.services.api.app.routes import discoveries_v1
        app.dependency_overrides[discoveries_v1.get_discovery_repository] = (
            lambda: mock_discovery_repo
        )

        try:
            client = TestClient(app)
            response = client.post("/discoveries/999/view?user_id=test_user")

            assert response.status_code == 404
            data = response.json()
            assert data["error"]["type"] == "NotFoundError"
        finally:
            app.dependency_overrides.clear()

    def test_set_feedback_success(self, mock_discovery_repo, sample_discovery_dto):
        """Set user feedback on discovery."""
        feedback_dto = DiscoveryDTO(
            id=sample_discovery_dto.id,
            user_id=sample_discovery_dto.user_id,
            discovery_type=sample_discovery_dto.discovery_type,
            title=sample_discovery_dto.title,
            description=sample_discovery_dto.description,
            confidence=sample_discovery_dto.confidence,
            relevance_score=sample_discovery_dto.relevance_score,
            viewed=sample_discovery_dto.viewed,
            user_reaction="helpful",  # Added reaction
            created_at=sample_discovery_dto.created_at,
            metadata=sample_discovery_dto.metadata,
        )
        mock_discovery_repo.set_reaction.return_value = feedback_dto

        from theo.services.api.app.routes import discoveries_v1
        app.dependency_overrides[discoveries_v1.get_discovery_repository] = (
            lambda: mock_discovery_repo
        )

        try:
            client = TestClient(app)
            response = client.post(
                "/discoveries/1/feedback?user_id=test_user&reaction=helpful"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["user_reaction"] == "helpful"

            mock_discovery_repo.set_reaction.assert_called_once_with(
                1, "test_user", "helpful"
            )
        finally:
            app.dependency_overrides.clear()


class TestRepositoryIntegration:
    """Test actual repository integration (requires database)."""

    @pytest.mark.slow
    def test_full_stack_list_discoveries(self, api_engine):
        """Full integration test with real repository and database."""
        from sqlalchemy.orm import Session
        from theo.adapters.persistence.discovery_repository import (
            SQLAlchemyDiscoveryRepository,
        )
        from theo.adapters.persistence.models import Discovery

        # Setup test data
        session = Session(api_engine)
        discovery = Discovery(
            user_id="integration_test",
            discovery_type="pattern",
            title="Integration Test Discovery",
            description="Testing full stack",
            confidence=0.9,
            relevance_score=0.8,
            viewed=False,
            created_at=datetime.now(UTC),
            meta={"integration": "test"},
        )
        session.add(discovery)
        session.commit()
        discovery_id = discovery.id

        try:
            # Test via repository
            repo = SQLAlchemyDiscoveryRepository(session)
            filters = DiscoveryListFilters(user_id="integration_test")
            results = repo.list(filters)

            assert len(results) == 1
            assert results[0].title == "Integration Test Discovery"
            assert isinstance(results[0], DiscoveryDTO)

            # Test mark viewed
            viewed_dto = repo.mark_viewed(discovery_id, "integration_test")
            assert viewed_dto.viewed is True

        finally:
            # Cleanup
            session.delete(discovery)
            session.commit()
            session.close()
