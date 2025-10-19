"""SQLAlchemy implementation of the ingestion job repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from theo.application.dtos import IngestionJobDTO
from theo.application.repositories import IngestionJobRepository
from .mappers import ingestion_job_to_dto
from .models import IngestionJob


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
    ) -> IngestionJobDTO | None:
        job = self.session.get(IngestionJob, job_id)
        if job is None:
            return None
        job.status = status
        if error is not None:
            job.error = error
        if document_id is not None:
            job.document_id = document_id
        job.updated_at = datetime.now(UTC)
        return ingestion_job_to_dto(job)

    def set_payload(self, job_id: str, payload: dict[str, Any]) -> IngestionJobDTO | None:
        job = self.session.get(IngestionJob, job_id)
        if job is None:
            return None
        job.payload = payload
        job.updated_at = datetime.now(UTC)
        return ingestion_job_to_dto(job)

    def merge_payload(self, job_id: str, payload: dict[str, Any]) -> IngestionJobDTO | None:
        job = self.session.get(IngestionJob, job_id)
        if job is None:
            return None
        merged: dict[str, Any] = dict(job.payload or {})
        merged.update(payload)
        job.payload = merged
        job.updated_at = datetime.now(UTC)
        return ingestion_job_to_dto(job)


__all__ = ["SQLAlchemyIngestionJobRepository"]
