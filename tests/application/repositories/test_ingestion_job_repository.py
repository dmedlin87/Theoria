"""Tests for the SQLAlchemy ingestion job repository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from theo.adapters.persistence.ingestion_job_repository import (
    SQLAlchemyIngestionJobRepository,
)
from theo.adapters.persistence.models import IngestionJob


pytestmark = pytest.mark.db


def _persist_job(session: Session, **overrides) -> IngestionJob:
    now = datetime.now(UTC)
    job = IngestionJob(
        id=overrides.get("id", "job-1"),
        job_type=overrides.get("job_type", "document_ingest"),
        status=overrides.get("status", "queued"),
        payload=overrides.get("payload"),
        error=overrides.get("error"),
        document_id=overrides.get("document_id"),
        created_at=overrides.get("created_at", now - timedelta(hours=1)),
        updated_at=overrides.get("updated_at", now - timedelta(hours=1)),
    )
    session.add(job)
    session.flush()
    return job


def test_update_status_updates_existing_row(session: Session) -> None:
    repo = SQLAlchemyIngestionJobRepository(session)
    job = _persist_job(session, id="job-update", error=None, document_id=None)
    original_updated_at = job.updated_at

    repo.update_status(
        "job-update",
        status="completed",
        error="none",
        document_id="doc-123",
    )

    refreshed = session.get(IngestionJob, "job-update")
    assert refreshed is not None
    assert refreshed.status == "completed"
    assert refreshed.error == "none"
    assert refreshed.document_id == "doc-123"
    assert refreshed.updated_at > original_updated_at


def test_update_status_missing_job_is_noop(session: Session) -> None:
    repo = SQLAlchemyIngestionJobRepository(session)

    repo.update_status("unknown", status="failed", error="boom")

    assert session.get(IngestionJob, "unknown") is None
    assert (
        session.scalar(select(func.count()).select_from(IngestionJob)) == 0
    )


def test_set_payload_replaces_existing_payload(session: Session) -> None:
    repo = SQLAlchemyIngestionJobRepository(session)
    job = _persist_job(session, id="job-payload", payload={"existing": True})
    original_updated_at = job.updated_at

    repo.set_payload("job-payload", {"new": "value"})

    refreshed = session.get(IngestionJob, "job-payload")
    assert refreshed is not None
    assert refreshed.payload == {"new": "value"}
    assert refreshed.updated_at > original_updated_at


def test_set_payload_missing_job_is_noop(session: Session) -> None:
    repo = SQLAlchemyIngestionJobRepository(session)

    repo.set_payload("unknown", {"new": 1})

    assert session.get(IngestionJob, "unknown") is None
    assert (
        session.scalar(select(func.count()).select_from(IngestionJob)) == 0
    )


def test_merge_payload_merges_existing_payload(session: Session) -> None:
    repo = SQLAlchemyIngestionJobRepository(session)
    job = _persist_job(
        session,
        id="job-merge",
        payload={"existing": 1, "override": "old"},
    )
    original_updated_at = job.updated_at

    repo.merge_payload("job-merge", {"override": "new", "extra": True})

    refreshed = session.get(IngestionJob, "job-merge")
    assert refreshed is not None
    assert refreshed.payload == {
        "existing": 1,
        "override": "new",
        "extra": True,
    }
    assert refreshed.updated_at > original_updated_at


def test_merge_payload_missing_job_is_noop(session: Session) -> None:
    repo = SQLAlchemyIngestionJobRepository(session)

    repo.merge_payload("unknown", {"override": 1})

    assert session.get(IngestionJob, "unknown") is None
    assert (
        session.scalar(select(func.count()).select_from(IngestionJob)) == 0
    )
