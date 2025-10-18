"""Unit tests for DiscoveryRepository implementations.

These tests verify repository behavior without requiring a real database,
demonstrating the improved testability of the new architecture.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock, call

import pytest

from theo.application.dtos import (
    CorpusSnapshotDTO,
    DiscoveryDTO,
    DiscoveryListFilters,
)
from theo.adapters.persistence.discovery_repository import SQLAlchemyDiscoveryRepository
from theo.adapters.persistence.models import Discovery, CorpusSnapshot


@pytest.fixture
def mock_session():
    """Provide a mock SQLAlchemy session."""
    return Mock()


@pytest.fixture
def sample_discovery_dto():
    """Provide a sample discovery DTO for testing."""
    return DiscoveryDTO(
        id=1,
        user_id="test_user",
        discovery_type="pattern",
        title="Test Pattern",
        description="A test pattern discovery",
        confidence=0.85,
        relevance_score=0.75,
        viewed=False,
        user_reaction=None,
        created_at=datetime.now(UTC),
        metadata={"test": "data"},
    )


@pytest.fixture
def sample_discovery_model():
    """Provide a sample discovery ORM model for testing."""
    return Discovery(
        id=1,
        user_id="test_user",
        discovery_type="pattern",
        title="Test Pattern",
        description="A test pattern discovery",
        confidence=0.85,
        relevance_score=0.75,
        viewed=False,
        user_reaction=None,
        created_at=datetime.now(UTC),
        meta={"test": "data"},
    )


class TestSQLAlchemyDiscoveryRepository:
    """Test SQLAlchemy implementation of DiscoveryRepository."""
    
    def test_initialization(self, mock_session):
        """Repository initializes with session."""
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        assert repo.session == mock_session
    
    def test_list_basic_filter(self, mock_session, sample_discovery_model):
        """List discoveries with basic user_id filter."""
        # Setup mock
        mock_result = Mock()
        mock_result.all.return_value = [sample_discovery_model]
        mock_session.scalars.return_value = mock_result
        
        # Execute
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        filters = DiscoveryListFilters(user_id="test_user")
        results = repo.list(filters)
        
        # Verify
        assert len(results) == 1
        assert isinstance(results[0], DiscoveryDTO)
        assert results[0].user_id == "test_user"
        assert results[0].title == "Test Pattern"
        
        # Verify query was executed
        mock_session.scalars.assert_called_once()
    
    def test_list_with_all_filters(self, mock_session, sample_discovery_model):
        """List discoveries with all filters applied."""
        mock_result = Mock()
        mock_result.all.return_value = [sample_discovery_model]
        mock_session.scalars.return_value = mock_result
        
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        filters = DiscoveryListFilters(
            user_id="test_user",
            discovery_type="pattern",
            viewed=False,
            min_confidence=0.5,
            limit=10,
            offset=5,
        )
        results = repo.list(filters)
        
        assert len(results) == 1
        assert results[0].discovery_type == "pattern"
    
    def test_get_by_id_found(self, mock_session, sample_discovery_model):
        """Get discovery by ID when it exists."""
        mock_result = Mock()
        mock_result.one_or_none.return_value = sample_discovery_model
        mock_session.scalars.return_value = mock_result
        
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        result = repo.get_by_id(discovery_id=1, user_id="test_user")
        
        assert result is not None
        assert isinstance(result, DiscoveryDTO)
        assert result.id == 1
    
    def test_get_by_id_not_found(self, mock_session):
        """Get discovery by ID when it doesn't exist."""
        mock_result = Mock()
        mock_result.one_or_none.return_value = None
        mock_session.scalars.return_value = mock_result
        
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        result = repo.get_by_id(discovery_id=999, user_id="test_user")
        
        assert result is None
    
    def test_create(self, mock_session, sample_discovery_dto):
        """Create a new discovery."""
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        result = repo.create(sample_discovery_dto)
        
        assert isinstance(result, DiscoveryDTO)
        mock_session.add_all.assert_called_once()
        mock_session.flush.assert_called_once()
        args, _ = mock_session.add_all.call_args
        assert len(args) == 1
        batch = args[0]
        assert isinstance(batch, list)
        assert len(batch) == 1

    def test_create_many(self, mock_session, sample_discovery_dto):
        """Create multiple discoveries in a single batch."""
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        other_dto = replace(
            sample_discovery_dto,
            id=2,
            title="Second Pattern",
            metadata={"other": "value"},
        )
        results = repo.create_many([sample_discovery_dto, other_dto])
        
        assert len(results) == 2
        mock_session.add_all.assert_called_once()
        mock_session.flush.assert_called_once()
        args, _ = mock_session.add_all.call_args
        assert len(args) == 1
        batch = args[0]
        assert isinstance(batch, list)
        assert len(batch) == 2
    
    def test_update(self, mock_session, sample_discovery_model, sample_discovery_dto):
        """Update an existing discovery."""
        mock_session.get.return_value = sample_discovery_model
        
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        updated_dto = DiscoveryDTO(
            id=1,
            user_id=sample_discovery_dto.user_id,
            discovery_type=sample_discovery_dto.discovery_type,
            title="Updated Title",
            description="Updated description",
            confidence=0.95,
            relevance_score=0.85,
            viewed=True,
            user_reaction="helpful",
            created_at=sample_discovery_dto.created_at,
            metadata={"updated": True},
        )
        
        result = repo.update(updated_dto)
        
        # Verify model was updated
        assert sample_discovery_model.title == "Updated Title"
        assert sample_discovery_model.viewed is True
        assert sample_discovery_model.user_reaction == "helpful"
        
        # Verify DTO returned
        assert isinstance(result, DiscoveryDTO)
        mock_session.flush.assert_called_once()
    
    def test_update_not_found(self, mock_session, sample_discovery_dto):
        """Update raises error when discovery doesn't exist."""
        mock_session.get.return_value = None
        
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        
        with pytest.raises(LookupError) as exc_info:
            repo.update(sample_discovery_dto)
        
        assert "not found" in str(exc_info.value).lower()
    
    def test_delete_by_types(self, mock_session):
        """Delete discoveries by type."""
        mock_result = Mock()
        mock_result.rowcount = 5
        mock_session.execute.return_value = mock_result
        
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        deleted_count = repo.delete_by_types(
            user_id="test_user",
            discovery_types=["pattern", "contradiction"]
        )
        
        assert deleted_count == 5
        mock_session.execute.assert_called_once()
    
    def test_mark_viewed(self, mock_session, sample_discovery_model):
        """Mark discovery as viewed."""
        mock_session.get.return_value = sample_discovery_model
        sample_discovery_model.viewed = False
        
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        result = repo.mark_viewed(discovery_id=1, user_id="test_user")
        
        # Verify model updated
        assert sample_discovery_model.viewed is True
        
        # Verify DTO returned
        assert isinstance(result, DiscoveryDTO)
        assert result.viewed is True
        mock_session.flush.assert_called_once()
    
    def test_mark_viewed_wrong_user(self, mock_session, sample_discovery_model):
        """Mark viewed raises error for wrong user."""
        sample_discovery_model.user_id = "other_user"
        mock_session.get.return_value = sample_discovery_model
        
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        
        with pytest.raises(LookupError):
            repo.mark_viewed(discovery_id=1, user_id="test_user")
    
    def test_set_reaction(self, mock_session, sample_discovery_model):
        """Set user reaction on discovery."""
        mock_session.get.return_value = sample_discovery_model
        
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        result = repo.set_reaction(
            discovery_id=1,
            user_id="test_user",
            reaction="helpful"
        )
        
        # Verify model updated
        assert sample_discovery_model.user_reaction == "helpful"
        
        # Verify DTO returned
        assert isinstance(result, DiscoveryDTO)
        assert result.user_reaction == "helpful"
        mock_session.flush.assert_called_once()
    
    def test_create_snapshot(self, mock_session):
        """Create a corpus snapshot."""
        snapshot_dto = CorpusSnapshotDTO(
            id=1,
            user_id="test_user",
            snapshot_date=datetime.now(UTC),
            document_count=100,
            verse_coverage={"unique_count": 50},
            dominant_themes={"top_topics": ["theology"]},
            metadata={"version": 1},
        )
        
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        result = repo.create_snapshot(snapshot_dto)
        
        assert isinstance(result, CorpusSnapshotDTO)
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
    
    def test_get_recent_snapshots(self, mock_session):
        """Get recent corpus snapshots."""
        snapshot_model = CorpusSnapshot(
            id=1,
            user_id="test_user",
            snapshot_date=datetime.now(UTC),
            document_count=100,
            verse_coverage={"unique_count": 50},
            dominant_themes={"top_topics": ["theology"]},
            meta={"version": 1},
        )
        
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([snapshot_model]))
        mock_session.scalars.return_value = mock_result
        
        repo = SQLAlchemyDiscoveryRepository(mock_session)
        results = repo.get_recent_snapshots(user_id="test_user", limit=5)
        
        assert len(results) == 1
        assert isinstance(results[0], CorpusSnapshotDTO)
        assert results[0].document_count == 100
