from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("THEO_FORCE_EMBEDDING_FALLBACK", "1")

from theo.application.facades import database as database_module  # noqa: E402
from theo.application.facades.database import (  # noqa: E402
    Base,
    configure_engine,
    get_engine,
    get_session,
)
from theo.application.facades.settings import get_settings  # noqa: E402
from theo.services.api.app.ingest import pipeline  # noqa: E402
from theo.services.api.app.ingest import events as ingest_events  # noqa: E402
from theo.services.api.app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def ingest_test_env(tmp_path_factory: pytest.TempPathFactory):
    tmp_dir = tmp_path_factory.mktemp("ingest-db")
    storage_root = tmp_path_factory.mktemp("ingest-storage")
    db_path = tmp_dir / "ingest.db"

    configure_engine(f"sqlite:///{db_path}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    settings = get_settings()
    original_storage = settings.storage_root
    storage_root.mkdir(parents=True, exist_ok=True)
    settings.storage_root = storage_root

    def _override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_session

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield {
                "client": client,
                "engine": engine,
                "storage_root": storage_root,
                "settings": settings,
                "original_storage": original_storage,
            }
    finally:
        app.dependency_overrides.pop(get_session, None)
        settings.storage_root = original_storage
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


@pytest.fixture()
def ingest_client(ingest_test_env):
    client = ingest_test_env["client"]
    engine = ingest_test_env["engine"]
    storage_root = ingest_test_env["storage_root"]

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    for path in storage_root.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    return client, storage_root


def test_duplicate_file_ingest_returns_400(ingest_client, monkeypatch):
    client, storage_root = ingest_client
    payload = b"Sample duplicate document"

    monkeypatch.setattr(
        ingest_events,
        "_dispatch_neighborhood_event",
        lambda payload: None,
    )

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

    monkeypatch.setattr(
        ingest_events,
        "_dispatch_neighborhood_event",
        lambda payload: None,
    )

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
