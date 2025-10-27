from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session
from theo.domain import Document, DocumentId, DocumentMetadata
from theo.platform.application import resolve_application
from theo.services.api.app.main import app
from theo.services.api.app.retriever import documents as documents_retriever
from theo.services.api.app.routes import documents as documents_route

from tests.integration._db import configure_temporary_engine

pytestmark = pytest.mark.schema


def test_documents_api_with_real_database_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure document APIs operate against a live transactional database."""

    real_get_document = documents_retriever.get_document

    def _get_document_with_missing(session: Session, document_id: str):
        if document_id == "missing":
            raise KeyError("Document missing")
        return real_get_document(session, document_id)

    monkeypatch.setattr(
        documents_retriever, "get_document", _get_document_with_missing
    )
    monkeypatch.setattr(documents_route, "get_document", _get_document_with_missing)

    engine = configure_temporary_engine(tmp_path / "api.db")
    container, registry = resolve_application()

    document = Document(
        id=DocumentId("doc-biblical"),
        metadata=DocumentMetadata(
            title="Genesis Commentary",
            source="manuscript",
            language="hebrew",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
        scripture_refs=("Gen.1.1",),
        tags=("creation", "theology"),
        checksum="abc123",
    )
    container.ingest_document(document)

    def _override_session() -> Iterator[Session]:
        with Session(registry.resolve("engine")) as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            headers = {"X-API-Key": "pytest-default-key"}
            response = client.get("/documents", headers=headers)
            assert response.status_code == 200
            payload = response.json()
            assert payload["items"], "Expected document results"
            first = payload["items"][0]
            assert first["id"] == str(document.id)
            assert first["title"] == document.metadata.title
            assert first["collection"] == document.metadata.source

            missing = client.get("/documents/missing", headers=headers)
            assert missing.status_code == 404
            detail = missing.json()
            assert detail["error"]["code"] == "RETRIEVAL_DOCUMENT_NOT_FOUND"
            assert "Document missing" in detail["detail"]
    finally:
        app.dependency_overrides.pop(get_session, None)
        engine.dispose()
