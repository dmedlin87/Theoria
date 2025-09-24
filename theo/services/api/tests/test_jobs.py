"""Tests for background job orchestration endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from theo.services.api.app.main import app


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as http_client:
        yield http_client


def _ingest_sample_document(client: TestClient) -> str:
    response = client.post(
        "/ingest/file",
        files={"file": ("sample.md", "Content about John 1:1", "text/markdown")},
    )
    assert response.status_code == 200, response.text
    return response.json()["document_id"]


def test_reparse_queues_job(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    document_id = _ingest_sample_document(client)

    captured: dict[str, Any] = {}

    def fake_delay(doc_id: str, path: str, frontmatter: Any = None) -> Any:
        captured["doc_id"] = doc_id
        captured["path"] = path
        captured["frontmatter"] = frontmatter
        class Result:
            id = "dummy"
        return Result()

    from theo.services.api.app.routes import jobs as jobs_module

    monkeypatch.setattr(jobs_module.process_file, "delay", fake_delay)

    response = client.post(f"/jobs/reparse/{document_id}")
    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload == {"document_id": document_id, "status": "queued"}

    assert captured["doc_id"] == document_id
    source_path = Path(captured["path"])
    assert source_path.exists()
    assert captured["frontmatter"] is None


def test_reparse_missing_document_returns_404(client: TestClient) -> None:
    response = client.post("/jobs/reparse/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"
