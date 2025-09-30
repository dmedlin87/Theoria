"""Tests for background job orchestration endpoints."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import threading
import time
from typing import Any, Callable, Iterator

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from theo.services.api.app.core.database import Base, get_engine
from theo.services.api.app.db.seeds import seed_reference_data
from theo.services.api.app.db.models import IngestionJob
from theo.services.api.app.routes import ingest, jobs as jobs_module
from theo.services.api.app.db.models import IngestionJob


@asynccontextmanager
async def _lifespan(_: FastAPI):
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        seed_reference_data(session)
    yield


def _create_app() -> FastAPI:
    app = FastAPI(lifespan=_lifespan)
    app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
    app.include_router(jobs_module.router, prefix="/jobs", tags=["jobs"])
    return app


app = _create_app()


class InstrumentedSendTask:
    """Test double that tracks Celery dispatch attempts."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._delay_seconds = 0.0
        self._block_event: threading.Event | None = None
        self._fail_after: int | None = None
        self._failure_factory: Callable[[], Exception] | None = None

    def set_delay(self, seconds: float) -> None:
        self._delay_seconds = seconds

    def block_until_released(self) -> threading.Event:
        event = threading.Event()
        self._block_event = event
        return event

    def release(self) -> None:
        if self._block_event is not None:
            self._block_event.set()

    def fail_after(self, count: int, factory: Callable[[], Exception]) -> None:
        self._fail_after = count
        self._failure_factory = factory

    def __call__(
        self,
        task_name: str,
        kwargs: dict[str, Any] | None = None,
        eta: datetime | None = None,
    ) -> Any:
        call = {"task": task_name, "kwargs": kwargs or {}, "eta": eta}
        with self._lock:
            call_index = len(self.calls)
            self.calls.append(call)

        if self._block_event is not None:
            if not self._block_event.wait(timeout=5):
                raise TimeoutError("send_task was never released during the test")

        if self._delay_seconds:
            time.sleep(self._delay_seconds)

        if self._fail_after is not None and call_index >= self._fail_after:
            assert self._failure_factory is not None
            raise self._failure_factory()

        class Result:
            id = f"instrumented-{call_index + 1}"

        return Result()


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as http_client:
        yield http_client


@pytest.fixture()
def instrumented_send_task(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[InstrumentedSendTask]:
    instrumented = InstrumentedSendTask()
    monkeypatch.setattr(jobs_module.celery, "send_task", instrumented)
    yield instrumented


def _ingest_sample_document(client: TestClient) -> str:
    unique_content = f"Content about John 1:1 -- {uuid4()}"
    response = client.post(
        "/ingest/file",
        files={"file": ("sample.md", unique_content, "text/markdown")},
    )
    assert response.status_code == 200, response.text
    return response.json()["document_id"]


def test_reparse_queues_job(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
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


def test_enqueue_endpoint_returns_idempotent_response(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    captured: list[dict[str, Any]] = []

    def fake_send_task(
        task_name: str,
        kwargs: dict[str, Any] | None = None,
        eta: datetime | None = None,
    ) -> Any:
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



def test_enqueue_collapses_concurrent_retries(
    client: TestClient, instrumented_send_task: InstrumentedSendTask
) -> None:
    payload = {
        "task": "research.enrich",
        "args": {"document_id": "doc-456"},
    }

    first = client.post("/jobs/enqueue", json=payload)
    assert first.status_code == 202, first.text
    first_payload = first.json()

    instrumented_send_task.set_delay(0.05)
    instrumented_send_task.fail_after(1, lambda: RuntimeError("should not re-dispatch"))

    def enqueue_again() -> dict[str, Any]:
        response = client.post("/jobs/enqueue", json=payload)
        assert response.status_code == 202, response.text
        return response.json()

def test_enqueue_endpoint_is_concurrent_safe(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    call_lock = threading.Lock()
    call_count = {"count": 0}

    def fake_send_task(
        task_name: str,
        kwargs: dict[str, Any] | None = None,
        eta: datetime | None = None,
    ) -> Any:
        with call_lock:
            call_count["count"] += 1

        class Result:
            id = "celery-task-concurrent"

        return Result()

    monkeypatch.setattr(jobs_module.celery, "send_task", fake_send_task)

    payload = {
        "task": "research.concurrent",
        "args": {"document_id": "doc-concurrent", "force": False},
    }

    def _enqueue() -> dict[str, Any]:
        response = client.post("/jobs/enqueue", json=payload)
        assert response.status_code == 202, response.text
        return response.json()

    first_payload = _enqueue()

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_enqueue) for _ in range(8)]
        results = [future.result() for future in futures]

    assert all(result == first_payload for result in results)
    assert call_count["count"] == 1

    with Session(get_engine()) as session:
        job_count = (
            session.query(IngestionJob)
            .filter(
                IngestionJob.job_type == payload["task"],
                IngestionJob.args_hash == first_payload["args_hash"],
            )
            .count()
        )

    assert job_count == 1


def test_enqueue_backpressure_returns_throttled_status(
    client: TestClient, instrumented_send_task: InstrumentedSendTask
) -> None:
    payload = {
        "task": "research.enrich",
        "args": {"document_id": "doc-789"},
    }

    instrumented_send_task.fail_after(0, lambda: RuntimeError("queue full"))

    response = client.post("/jobs/enqueue", json=payload)
    assert response.status_code == 503
    assert response.json()["detail"] == "Unable to enqueue job"

def test_topic_digest_job_enqueues(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
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


def test_summary_job_enqueues(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    document_id = _ingest_sample_document(client)
    captured: dict[str, Any] = {}

    def fake_delay(doc_id: str, job_id: str) -> Any:
        captured["document_id"] = doc_id
        captured["job_id"] = job_id

        class Result:
            id = "summary-job"

        return Result()

    monkeypatch.setattr(jobs_module.summary_task, "delay", fake_delay)

    response = client.post("/jobs/summaries", json={"document_id": document_id})
    assert response.status_code == 202, response.text
    payload = response.json()

    assert payload["job_type"] == "summary"
    assert payload["document_id"] == document_id

    assert captured["document_id"] == document_id
    assert captured["job_id"] == payload["id"]

