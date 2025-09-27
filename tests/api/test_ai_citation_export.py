from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core.database import Base, get_session
from theo.services.api.app.db.models import Document, Passage
from theo.services.api.app.main import app


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        document = Document(
            id="doc-1",
            title="Sample Document",
            authors=["Jane Doe"],
            doi="10.1234/example",
            source_url="https://example.test",
            source_type="article",
            collection="Test",
            year=2024,
            abstract="Example abstract",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        passage = Passage(
            id="passage-1",
            document_id="doc-1",
            text="In the beginning was the Word.",
            osis_ref="John.1.1",
            page_no=1,
            t_start=0.0,
            t_end=5.0,
        )
        session.add(document)
        session.add(passage)
        session.commit()

    def _override_session():
        db_session = TestingSession()
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
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_export_citations_returns_csl_payload(client: TestClient) -> None:
    response = client.post(
        "/ai/citations/export",
        json={
            "citations": [
                {
                    "index": 1,
                    "osis": "John.1.1",
                    "anchor": "John 1:1",
                    "passage_id": "passage-1",
                    "document_id": "doc-1",
                    "document_title": "Sample Document",
                    "snippet": "In the beginning was the Word.",
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["manifest"]["type"] == "documents"
    assert payload["records"][0]["document_id"] == "doc-1"
    passage_meta = payload["records"][0]["passages"][0]["meta"]
    assert passage_meta["anchor"] == "John 1:1"
    assert payload["csl"][0]["title"] == "Sample Document"
    assert payload["csl"][0]["DOI"] == "10.1234/example"
    assert payload["manager_payload"]["format"] == "csl-json"
    assert payload["manager_payload"]["zotero"]["items"][0]["id"] == "doc-1"


def test_export_citations_allows_missing_source_url(client: TestClient) -> None:
    response = client.post(
        "/ai/citations/export",
        json={
            "citations": [
                {
                    "index": 1,
                    "osis": "John.1.1",
                    "anchor": "John 1:1",
                    "passage_id": "passage-1",
                    "document_id": "doc-1",
                    "document_title": "Sample Document",
                    "snippet": "In the beginning was the Word.",
                    "source_url": None,
                }
            ]
        },
    )

    assert response.status_code == 200


def test_export_citations_rejects_empty_payload(client: TestClient) -> None:
    response = client.post("/ai/citations/export", json={"citations": []})
    assert response.status_code == 400


def test_export_citations_reports_missing_document(client: TestClient) -> None:
    response = client.post(
        "/ai/citations/export",
        json={
            "citations": [
                {
                    "index": 1,
                    "osis": "John.1.1",
                    "anchor": "John 1:1",
                    "passage_id": "missing",
                    "document_id": "doc-unknown",
                    "document_title": "Missing",
                    "snippet": "Unknown",
                }
            ]
        },
    )
    assert response.status_code == 404
