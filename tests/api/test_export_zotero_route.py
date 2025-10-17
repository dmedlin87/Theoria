"""Tests for Zotero export API endpoint."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
import sys
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades.database import get_session
from theo.adapters.persistence.models import Document
from theo.services.api.app.main import app


@pytest.fixture()
def client(api_engine) -> Generator[TestClient, None, None]:
    """Test client with sample documents."""
    engine = api_engine
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    with Session(engine) as session:
        doc1 = Document(
            id="doc-1",
            title="Systematic Theology Vol 1",
            authors=["Louis Berkhof"],
            doi="10.1234/berkhof.vol1",
            source_url="https://example.com/berkhof",
            source_type="book",
            collection="Theology",
            year=1938,
            abstract="A comprehensive Reformed systematic theology.",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        doc2 = Document(
            id="doc-2",
            title="Institutes of the Christian Religion",
            authors=["John Calvin"],
            source_type="book",
            collection="Theology",
            year=1536,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(doc1)
        session.add(doc2)
        session.commit()

    def _override_session() -> Generator[Session, None, None]:
        db_session = session_factory()
        try:
            yield db_session
        finally:
            db_session.close()

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_export_to_zotero_success(client: TestClient):
    """Test successful Zotero export."""
    mock_result = {
        "success": True,
        "exported_count": 2,
        "failed_count": 0,
        "errors": [],
    }
    
    with patch("theo.services.api.app.routes.export.export_to_zotero") as mock_export:
        mock_export.return_value = mock_result
        
        response = client.post(
            "/api/export/zotero",
            json={
                "document_ids": ["doc-1", "doc-2"],
                "api_key": "test-api-key",
                "user_id": "12345",
            },
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["exported_count"] == 2
    assert data["failed_count"] == 0
    assert data["errors"] == []


def test_export_to_zotero_missing_user_and_group(client: TestClient):
    """Test Zotero export without user_id or group_id."""
    response = client.post(
        "/api/export/zotero",
        json={
            "document_ids": ["doc-1"],
            "api_key": "test-key",
        },
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "user_id or group_id" in data["detail"].lower()


def test_export_to_zotero_empty_document_list(client: TestClient):
    """Test Zotero export with no documents."""
    response = client.post(
        "/api/export/zotero",
        json={
            "document_ids": [],
            "api_key": "test-key",
            "user_id": "12345",
        },
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "no documents" in data["detail"].lower()


def test_export_to_zotero_unknown_documents(client: TestClient):
    """Test Zotero export with non-existent document IDs."""
    response = client.post(
        "/api/export/zotero",
        json={
            "document_ids": ["nonexistent-1", "nonexistent-2"],
            "api_key": "test-key",
            "user_id": "12345",
        },
    )
    
    assert response.status_code == 404
    data = response.json()
    assert "unknown document" in data["detail"].lower()


def test_export_to_zotero_partial_unknown_documents(client: TestClient):
    """Test Zotero export with mix of valid and invalid document IDs."""
    response = client.post(
        "/api/export/zotero",
        json={
            "document_ids": ["doc-1", "nonexistent-1"],
            "api_key": "test-key",
            "user_id": "12345",
        },
    )
    
    assert response.status_code == 404
    data = response.json()
    assert "nonexistent-1" in data["detail"]


def test_export_to_zotero_group_library(client: TestClient):
    """Test Zotero export to group library."""
    mock_result = {
        "success": True,
        "exported_count": 1,
        "failed_count": 0,
        "errors": [],
    }
    
    with patch("theo.services.api.app.routes.export.export_to_zotero") as mock_export:
        mock_export.return_value = mock_result
        
        response = client.post(
            "/api/export/zotero",
            json={
                "document_ids": ["doc-1"],
                "api_key": "test-api-key",
                "group_id": "67890",
            },
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["exported_count"] == 1


def test_export_to_zotero_with_failures(client: TestClient):
    """Test Zotero export with some failed items."""
    mock_result = {
        "success": True,
        "exported_count": 1,
        "failed_count": 1,
        "errors": ["Item 1 failed validation"],
    }
    
    with patch("theo.services.api.app.routes.export.export_to_zotero") as mock_export:
        mock_export.return_value = mock_result
        
        response = client.post(
            "/api/export/zotero",
            json={
                "document_ids": ["doc-1", "doc-2"],
                "api_key": "test-api-key",
                "user_id": "12345",
            },
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["exported_count"] == 1
    assert data["failed_count"] == 1
    assert len(data["errors"]) == 1


def test_export_to_zotero_api_error(client: TestClient):
    """Test Zotero export when API call fails."""
    from theo.services.api.app.export.zotero import ZoteroExportError
    
    with patch("theo.services.api.app.routes.export.export_to_zotero") as mock_export:
        mock_export.side_effect = ZoteroExportError("Invalid API key")
        
        response = client.post(
            "/api/export/zotero",
            json={
                "document_ids": ["doc-1"],
                "api_key": "invalid-key",
                "user_id": "12345",
            },
        )
    
    assert response.status_code == 400
    data = response.json()
    assert "invalid api key" in data["detail"].lower()


def test_export_to_zotero_request_validation():
    """Test Zotero export request validation."""
    from theo.services.api.app.models.export import ZoteroExportRequest
    from pydantic import ValidationError
    
    # Valid request
    valid_request = ZoteroExportRequest(
        document_ids=["doc-1", "doc-2"],
        api_key="test-key",
        user_id="12345",
    )
    assert valid_request.document_ids == ["doc-1", "doc-2"]
    assert valid_request.api_key == "test-key"
    assert valid_request.user_id == "12345"
    
    # Empty document list should fail
    with pytest.raises(ValidationError):
        ZoteroExportRequest(
            document_ids=[],
            api_key="test-key",
            user_id="12345",
        )
    
    # Missing API key should fail
    with pytest.raises(ValidationError):
        ZoteroExportRequest(
            document_ids=["doc-1"],
            user_id="12345",
        )


def test_export_to_zotero_both_user_and_group(client: TestClient):
    """Test Zotero export with both user_id and group_id provided."""
    mock_result = {
        "success": True,
        "exported_count": 1,
        "failed_count": 0,
        "errors": [],
    }
    
    with patch("theo.services.api.app.routes.export.export_to_zotero") as mock_export:
        mock_export.return_value = mock_result
        
        # Should succeed - endpoint accepts either one
        response = client.post(
            "/api/export/zotero",
            json={
                "document_ids": ["doc-1"],
                "api_key": "test-api-key",
                "user_id": "12345",
                "group_id": "67890",
            },
        )
    
    assert response.status_code == 200


def test_export_to_zotero_response_model():
    """Test Zotero export response model."""
    from theo.services.api.app.models.export import ZoteroExportResponse
    
    response = ZoteroExportResponse(
        success=True,
        exported_count=5,
        failed_count=2,
        errors=["Error 1", "Error 2"],
    )
    
    assert response.success is True
    assert response.exported_count == 5
    assert response.failed_count == 2
    assert len(response.errors) == 2
    
    # Test defaults
    response_minimal = ZoteroExportResponse(
        success=False,
        exported_count=0,
    )
    
    assert response_minimal.failed_count == 0
    assert response_minimal.errors == []


def test_export_to_zotero_extracts_citation_sources(client: TestClient):
    """Test that export correctly extracts citation sources from documents."""
    mock_result = {
        "success": True,
        "exported_count": 2,
        "failed_count": 0,
        "errors": [],
    }
    
    with patch("theo.services.api.app.routes.export.export_to_zotero") as mock_export:
        mock_export.return_value = mock_result
        
        response = client.post(
            "/api/export/zotero",
            json={
                "document_ids": ["doc-1", "doc-2"],
                "api_key": "test-api-key",
                "user_id": "12345",
            },
        )
    
    assert response.status_code == 200
    
    # Verify export_to_zotero was called with correct arguments
    call_args = mock_export.call_args
    sources = call_args.kwargs["sources"]
    csl_entries = call_args.kwargs["csl_entries"]
    
    assert len(sources) == 2
    assert len(csl_entries) == 2
    assert call_args.kwargs["api_key"] == "test-api-key"
    assert call_args.kwargs["user_id"] == "12345"
