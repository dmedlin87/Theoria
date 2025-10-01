from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core.database import (  # noqa: E402
    Base,
    configure_engine,
    get_engine,
    get_session,
)
from theo.services.api.app.core.settings import get_settings  # noqa: E402
from theo.services.api.app.ingest import pipeline  # noqa: E402
from theo.services.api.app.main import app  # noqa: E402


@pytest.fixture()
def ingest_client(tmp_path: Path):
    db_path = tmp_path / "ingest.db"
    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    settings = get_settings()
    original_storage = settings.storage_root
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    settings.storage_root = storage_root

    def _override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_session

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, storage_root
    finally:
        app.dependency_overrides.pop(get_session, None)
        settings.storage_root = original_storage


def test_duplicate_file_ingest_returns_400(ingest_client):
    client, storage_root = ingest_client
    payload = b"Sample duplicate document"

    before = list(storage_root.iterdir())
    assert before == []

    response = client.post(
        "/ingest/file",
        files={"file": ("doc.txt", payload, "text/plain")},
    )
    assert response.status_code == 200, response.text

    stored_dirs = list(storage_root.iterdir())
    assert len(stored_dirs) == 1

    duplicate_response = client.post(
        "/ingest/file",
        files={"file": ("doc.txt", payload, "text/plain")},
    )

    assert duplicate_response.status_code == 400, duplicate_response.text
    assert duplicate_response.json().get("detail") == "Document already ingested"

    after_dirs = list(storage_root.iterdir())
    assert [path for path in after_dirs if path.is_dir()] == stored_dirs


def test_duplicate_url_ingest_returns_400(ingest_client, monkeypatch):
    client, storage_root = ingest_client

    html = "<html><body><p>Hello world</p></body></html>"
    metadata = {"title": "Example", "canonical_url": "https://example.com/article"}

    def _fake_fetch(settings, url: str):
        return html, metadata

    monkeypatch.setattr(pipeline, "_fetch_web_document", _fake_fetch)

    first = client.post(
        "/ingest/url",
        json={"url": "https://example.com/article"},
    )
    assert first.status_code == 200, first.text

    stored_dirs = list(storage_root.iterdir())
    assert len(stored_dirs) == 1

    second = client.post(
        "/ingest/url",
        json={"url": "https://example.com/article"},
    )

    assert second.status_code == 400, second.text
    assert second.json().get("detail") == "Document already ingested"

    after_dirs = list(storage_root.iterdir())
    assert [path for path in after_dirs if path.is_dir()] == stored_dirs
