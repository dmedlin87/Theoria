"""SQLAlchemy implementation of the ingestion job repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy.orm import Session

from theo.application.repositories import IngestionJobRepository

from .models import IngestionJob


if TYPE_CHECKING:
    from theo.application.dtos import IngestionJobDTO


class SQLAlchemyIngestionJobRepository(IngestionJobRepository):
    """Persistence adapter for ingestion job bookkeeping."""

    def __init__(self, session: Session):
        self.session = session

    def update_status(
        self,
        job_id: str,
        *,
        status: str,
        error: str | None = None,
        document_id: str | None = None,
    ) -> None:
        job = self.session.get(IngestionJob, job_id)
        if job is None:
            return
        job.status = status
        if error is not None:
            job.error = error
        if document_id is not None:
            job.document_id = document_id
        job.updated_at = datetime.now(UTC)

    def set_payload(self, job_id: str, payload: dict[str, Any]) -> None:
        job = self.session.get(IngestionJob, job_id)
        if job is None:
            return
        job.payload = payload
        job.updated_at = datetime.now(UTC)

    def merge_payload(self, job_id: str, payload: dict[str, Any]) -> None:
        job = self.session.get(IngestionJob, job_id)
        if job is None:
            return
        merged: dict[str, Any] = dict(job.payload or {})
        merged.update(payload)
        job.payload = merged
        job.updated_at = datetime.now(UTC)


__all__ = ["SQLAlchemyIngestionJobRepository"]

