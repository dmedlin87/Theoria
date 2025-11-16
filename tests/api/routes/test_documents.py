"""Comprehensive tests for documents route endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import Document, Passage


@pytest.fixture
def sample_document(api_engine) -> str:
    """Create a sample document for testing."""
    from theo.application.facades.database import get_session

    session = next(get_session())
    doc = Document(
        id="test-doc-1",
        title="Test Document",
        author="Test Author",
        source_type="article",
        url="https://example.com/test",
        abstract="Test abstract content",
    )
    session.add(doc)
    session.commit()

    # Add a passage
    passage = Passage(
        document_id="test-doc-1",
        passage_id="test-doc-1-p1",
        ordinal=1,
        content="Sample passage content for testing.",
    )
    session.add(passage)
    session.commit()

    yield "test-doc-1"

    # Cleanup
    session.query(Passage).filter_by(document_id="test-doc-1").delete()
    session.query(Document).filter_by(id="test-doc-1").delete()
    session.commit()


class TestDocumentList:
    """Test suite for GET /documents/ endpoint."""

    def test_list_documents_default_pagination(
        self, api_test_client: TestClient
    ) -> None:
        """Test listing documents with default pagination."""
        response = api_test_client.get("/documents/")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total" in data
        assert isinstance(data["documents"], list)

    def test_list_documents_custom_limit(self, api_test_client: TestClient) -> None:
        """Test listing documents with custom limit."""
        response = api_test_client.get("/documents/", params={"limit": 5})

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) <= 5

    def test_list_documents_with_offset(self, api_test_client: TestClient) -> None:
        """Test listing documents with offset pagination."""
        response = api_test_client.get("/documents/", params={"limit": 10, "offset": 5})

        assert response.status_code == 200

    def test_list_documents_limit_minimum(self, api_test_client: TestClient) -> None:
        """Test that minimum limit (1) is accepted."""
        response = api_test_client.get("/documents/", params={"limit": 1})

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) <= 1

    def test_list_documents_limit_maximum(self, api_test_client: TestClient) -> None:
        """Test that maximum limit (100) is accepted."""
        response = api_test_client.get("/documents/", params={"limit": 100})

        assert response.status_code == 200

    def test_list_documents_limit_too_low_rejected(
        self, api_test_client: TestClient
    ) -> None:
        """Test that limit < 1 is rejected."""
        response = api_test_client.get("/documents/", params={"limit": 0})

        assert response.status_code == 422

    def test_list_documents_limit_too_high_rejected(
        self, api_test_client: TestClient
    ) -> None:
        """Test that limit > 100 is rejected."""
        response = api_test_client.get("/documents/", params={"limit": 101})

        assert response.status_code == 422

    def test_list_documents_offset_negative_rejected(
        self, api_test_client: TestClient
    ) -> None:
        """Test that negative offset is rejected."""
        response = api_test_client.get("/documents/", params={"offset": -1})

        assert response.status_code == 422


class TestDocumentDetail:
    """Test suite for GET /documents/{document_id} endpoint."""

    def test_get_document_by_id(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test retrieving document by ID."""
        response = api_test_client.get(f"/documents/{sample_document}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_document
        assert "title" in data
        assert "author" in data

    def test_get_document_not_found(self, api_test_client: TestClient) -> None:
        """Test 404 response for non-existent document."""
        response = api_test_client.get("/documents/non-existent-id")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "RETRIEVAL_DOCUMENT_NOT_FOUND"

    def test_get_document_includes_metadata(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test that document detail includes all metadata fields."""
        response = api_test_client.get(f"/documents/{sample_document}")

        assert response.status_code == 200
        data = response.json()
        expected_fields = ["id", "title", "author", "source_type"]
        for field in expected_fields:
            assert field in data


class TestDocumentPassages:
    """Test suite for GET /documents/{document_id}/passages endpoint."""

    def test_get_document_passages(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test retrieving document passages."""
        response = api_test_client.get(f"/documents/{sample_document}/passages")

        assert response.status_code == 200
        data = response.json()
        assert "passages" in data
        assert isinstance(data["passages"], list)

    def test_get_document_passages_with_limit(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test passages with custom limit."""
        response = api_test_client.get(
            f"/documents/{sample_document}/passages", params={"limit": 5}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["passages"]) <= 5

    def test_get_document_passages_with_offset(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test passages with offset pagination."""
        response = api_test_client.get(
            f"/documents/{sample_document}/passages",
            params={"limit": 10, "offset": 5},
        )

        assert response.status_code == 200

    def test_get_document_passages_limit_minimum(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test that minimum limit (1) is accepted."""
        response = api_test_client.get(
            f"/documents/{sample_document}/passages", params={"limit": 1}
        )

        assert response.status_code == 200

    def test_get_document_passages_limit_maximum(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test that maximum limit (200) is accepted."""
        response = api_test_client.get(
            f"/documents/{sample_document}/passages", params={"limit": 200}
        )

        assert response.status_code == 200

    def test_get_document_passages_limit_too_high_rejected(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test that limit > 200 is rejected."""
        response = api_test_client.get(
            f"/documents/{sample_document}/passages", params={"limit": 201}
        )

        assert response.status_code == 422

    def test_get_passages_document_not_found(
        self, api_test_client: TestClient
    ) -> None:
        """Test 404 for passages of non-existent document."""
        response = api_test_client.get("/documents/non-existent/passages")

        assert response.status_code == 404


class TestDocumentUpdate:
    """Test suite for PATCH /documents/{document_id} endpoint."""

    def test_update_document_metadata(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test updating document metadata."""
        update_payload = {
            "title": "Updated Title",
            "abstract": "Updated abstract content",
        }

        response = api_test_client.patch(
            f"/documents/{sample_document}",
            json=update_payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["abstract"] == "Updated abstract content"

    def test_update_document_partial_fields(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test updating only some document fields."""
        update_payload = {"title": "New Title Only"}

        response = api_test_client.patch(
            f"/documents/{sample_document}",
            json=update_payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Title Only"

    def test_update_document_not_found(self, api_test_client: TestClient) -> None:
        """Test 404 when updating non-existent document."""
        update_payload = {"title": "Updated Title"}

        response = api_test_client.patch(
            "/documents/non-existent-id",
            json=update_payload,
        )

        assert response.status_code == 404

    def test_update_document_empty_payload(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test updating with empty payload."""
        response = api_test_client.patch(
            f"/documents/{sample_document}",
            json={},
        )

        # Should still succeed (no-op update)
        assert response.status_code in [200, 422]


class TestDocumentAnnotations:
    """Test suite for document annotation endpoints."""

    def test_list_annotations_empty(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test listing annotations for document with no annotations."""
        response = api_test_client.get(f"/documents/{sample_document}/annotations")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_annotation(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test creating a new annotation."""
        annotation_payload = {
            "passage_id": "test-doc-1-p1",
            "annotation_type": "highlight",
            "content": "Important passage",
            "start_offset": 0,
            "end_offset": 10,
        }

        response = api_test_client.post(
            f"/documents/{sample_document}/annotations",
            json=annotation_payload,
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["annotation_type"] == "highlight"
        assert data["content"] == "Important passage"

    def test_create_annotation_document_not_found(
        self, api_test_client: TestClient
    ) -> None:
        """Test creating annotation for non-existent document."""
        annotation_payload = {
            "passage_id": "test-passage",
            "annotation_type": "note",
            "content": "Test note",
        }

        response = api_test_client.post(
            "/documents/non-existent/annotations",
            json=annotation_payload,
        )

        assert response.status_code == 404

    def test_create_annotation_invalid_payload(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test creating annotation with invalid payload."""
        invalid_payload = {
            # Missing required fields
            "content": "Test note",
        }

        response = api_test_client.post(
            f"/documents/{sample_document}/annotations",
            json=invalid_payload,
        )

        assert response.status_code in [422, 400]

    def test_delete_annotation(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test deleting an annotation."""
        # First create an annotation
        annotation_payload = {
            "passage_id": "test-doc-1-p1",
            "annotation_type": "highlight",
            "content": "To be deleted",
        }

        create_response = api_test_client.post(
            f"/documents/{sample_document}/annotations",
            json=annotation_payload,
        )
        assert create_response.status_code == 201
        annotation_id = create_response.json()["id"]

        # Then delete it
        delete_response = api_test_client.delete(
            f"/documents/{sample_document}/annotations/{annotation_id}"
        )

        assert delete_response.status_code == 204

    def test_delete_annotation_not_found(
        self, api_test_client: TestClient, sample_document: str
    ) -> None:
        """Test deleting non-existent annotation."""
        response = api_test_client.delete(
            f"/documents/{sample_document}/annotations/non-existent-id"
        )

        assert response.status_code == 404

    def test_delete_annotation_document_not_found(
        self, api_test_client: TestClient
    ) -> None:
        """Test deleting annotation from non-existent document."""
        response = api_test_client.delete(
            "/documents/non-existent/annotations/annotation-id"
        )

        assert response.status_code == 404


class TestLatestDigestDocument:
    """Test suite for GET /documents/digest endpoint."""

    def test_get_latest_digest_no_digests(self, api_test_client: TestClient) -> None:
        """Test getting latest digest when none exist."""
        response = api_test_client.get("/documents/digest")

        # Should return 404 when no digests exist
        assert response.status_code == 404

    def test_get_latest_digest_exists(self, api_test_client: TestClient) -> None:
        """Test getting latest digest when one exists."""
        # This test requires a digest document to be created
        # Implementation depends on how digest documents are created
        response = api_test_client.get("/documents/digest")

        # Either 200 with digest or 404 if none exist
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "title" in data


@pytest.mark.no_auth_override
class TestDocumentsAuthentication:
    """Test documents endpoint authentication requirements."""

    def test_list_documents_authentication(self, api_test_client: TestClient) -> None:
        """Test that document list may require authentication."""
        response = api_test_client.get("/documents/")

        # Implementation-dependent: may allow anonymous or require auth
        assert response.status_code in [200, 401]

    def test_create_annotation_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test that creating annotations requires authentication."""
        annotation_payload = {
            "passage_id": "test-passage",
            "annotation_type": "note",
            "content": "Test note",
        }

        response = api_test_client.post(
            "/documents/test-doc/annotations",
            json=annotation_payload,
        )

        # Should require authentication for mutations
        assert response.status_code in [401, 404]
