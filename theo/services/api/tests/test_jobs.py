"""Tests for background job orchestration endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from theo.services.api.app.main import app
from theo.services.api.app.routes import jobs as jobs_module


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


def test_enqueue_endpoint_returns_idempotent_response(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    captured: list[dict[str, Any]] = []

    def fake_send_task(task_name: str, kwargs: dict[str, Any] | None = None, eta: datetime | None = None) -> Any:
        captured.append({"task": task_name, "kwargs": kwargs, "eta": eta})

        class Result:
            id = "celery-task-1"

        return Result()

    monkeypatch.setattr(jobs_module.celery, "send_task", fake_send_task)

    payload = {
        "task": "research.enrich",
        "args": {"document_id": "doc-123", "force": True},
        "schedule_at": datetime(2030, 1, 1, 12, 0, tzinfo=UTC).isoformat(),
    }

    first = client.post("/jobs/enqueue", json=payload)
    assert first.status_code == 202, first.text
    first_payload = first.json()
    assert first_payload["task"] == "research.enrich"
    assert first_payload["status_url"].endswith(first_payload["job_id"])
    assert len(first_payload["args_hash"]) == 64
    assert captured[0]["kwargs"] == {"document_id": "doc-123", "force": True}

    second = client.post("/jobs/enqueue", json=payload)
    assert second.status_code == 202
    assert second.json() == first_payload
    assert len(captured) == 1, "Duplicate enqueue should not dispatch twice"


def test_topic_digest_job_enqueues(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    captured: dict[str, Any] = {}

    def fake_delay(**kwargs: Any) -> Any:
        captured.update(kwargs)

        class Result:
            id = "topic-digest-job"

        return Result()

    monkeypatch.setattr(jobs_module.topic_digest_task, "delay", fake_delay)

    since = datetime(2024, 8, 5, tzinfo=UTC)
    response = client.post(
        "/jobs/topic_digest",
        json={"since": since.isoformat(), "notify": ["alerts@theo.app", ""]},
    )

    assert response.status_code == 202, response.text
    payload = response.json()

    assert payload["job_type"] == "topic_digest"
    assert payload["status"] == "queued"
    assert payload["payload"]["since"] == since.isoformat()
    assert payload["payload"]["notify"] == ["alerts@theo.app"]

    assert captured["job_id"] == payload["id"]
    assert captured["since"] == since.isoformat()
    assert captured["notify"] == ["alerts@theo.app"]
