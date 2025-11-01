"""Regression tests for Celery task retry and idempotency behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from celery.app.task import Task
from celery.exceptions import Retry as CeleryRetry
from sqlalchemy.orm import Session

pytest_plugins = ("celery.contrib.pytest",)

from theo.adapters.persistence.models import AppSetting, IngestionJob
from theo.application.facades.database import Base
from theo.infrastructure.api.app.analytics.topics import TopicDigest
from theo.infrastructure.api.app.workers import tasks


def _task(obj: Any) -> Task:
    """Return a Celery task with typing information for static analysis."""

    return cast(Task, obj)


@pytest.fixture
# This fixture intentionally overrides the pytest-celery plugin's celery_app fixture.
def celery_app():  # type: ignore[override]
    """Run Celery tasks eagerly against the application task registry."""

    app = tasks.celery
    original_always_eager = app.conf.task_always_eager
    original_propagates = app.conf.task_eager_propagates
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True
    try:
        yield app
    finally:
        app.conf.task_always_eager = original_always_eager
        app.conf.task_eager_propagates = original_propagates


@pytest.mark.celery
@pytest.mark.pgvector
def test_process_url_retry_uses_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch,
    celery_app,
    celery_worker,
    pgvector_engine,
) -> None:
    """``process_url`` raises ``Retry`` with the configured backoff window."""

    Base.metadata.drop_all(bind=pgvector_engine)
    Base.metadata.create_all(bind=pgvector_engine)

    monkeypatch.setattr(tasks, "get_engine", lambda: pgvector_engine)

    failure = RuntimeError("transient outage")
    attempts = 0

    def failing_pipeline(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise failure

    monkeypatch.setattr(
        "theo.infrastructure.api.app.ingest.pipeline.run_pipeline_for_url",
        failing_pipeline,
    )

    with Session(pgvector_engine) as session:
        job = IngestionJob(job_type="url_ingest", status="queued")
        session.add(job)
        session.commit()
        job_id = job.id

    task = _task(tasks.process_url)

    with pytest.raises(CeleryRetry) as excinfo:
        task.apply(
            args=("doc-123", "https://example.invalid/resource"),
            kwargs={"job_id": job_id},
            throw=True,
        )

    assert attempts == 1

    retry_exc = excinfo.value
    assert retry_exc.when == 1
    assert retry_exc.is_eager is True
    assert retry_exc.sig.options["countdown"] == 1
    assert retry_exc.sig.options["retries"] == 1

    with Session(pgvector_engine) as session:
        job = session.get(IngestionJob, job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.error == str(failure)

    # Simulate a retry by passing the retries count via options, as Celery would do.

    with pytest.raises(CeleryRetry) as second_exc:
        task.apply(
            args=("doc-123", "https://example.invalid/resource"),
            kwargs={"job_id": job_id},
            throw=True,
            options={"retries": 1},
        )

    assert attempts == 2

    retry_again = second_exc.value
    assert retry_again.when == 2
    assert retry_again.sig.options["countdown"] == 2
    assert retry_again.sig.options["retries"] == 2

    with Session(pgvector_engine) as session:
        jobs = session.query(IngestionJob).all()
        assert len(jobs) == 1
        assert jobs[0].status == "failed"
        assert jobs[0].error == str(failure)


@pytest.mark.celery
@pytest.mark.pgvector
def test_topic_digest_task_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    celery_app,
    celery_worker,
    pgvector_engine,
) -> None:
    """Running the topic digest task twice persists a single snapshot."""

    Base.metadata.drop_all(bind=pgvector_engine)
    Base.metadata.create_all(bind=pgvector_engine)

    monkeypatch.setattr(tasks, "get_engine", lambda: pgvector_engine)

    digest = TopicDigest(
        generated_at=datetime.now(UTC),
        window_start=datetime.now(UTC),
        topics=[],
    )
    invocation_windows: list[datetime] = []

    def fake_generate_topic_digest(session, window_start):
        invocation_windows.append(window_start)
        return digest

    monkeypatch.setattr(
        "theo.infrastructure.api.app.workers.tasks.generate_topic_digest",
        fake_generate_topic_digest,
    )

    def fake_upsert_digest_document(_session, _digest):
        class _Document:
            id = "digest-doc"

        return _Document()

    monkeypatch.setattr(
        "theo.infrastructure.api.app.workers.tasks.upsert_digest_document",
        fake_upsert_digest_document,
    )

    published_events: list[Any] = []

    class _Publisher:
        def publish(self, event):
            published_events.append(event)

    monkeypatch.setattr(
        "theo.infrastructure.api.app.analytics.topics.get_event_publisher",
        lambda: _Publisher(),
    )

    task = _task(tasks.topic_digest)
    task.apply(kwargs={"hours": 12}, throw=True)
    task.apply(kwargs={"hours": 12}, throw=True)

    assert len(invocation_windows) == 2
    assert published_events  # events are still emitted for monitoring

    with Session(pgvector_engine) as session:
        rows = session.query(AppSetting).all()
        assert len(rows) == 1
        stored = rows[0]

    assert stored.key == "app:topic-digest"
    assert stored.value == digest.model_dump(mode="json")
