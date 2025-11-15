"""SQLAlchemy implementation of the ingestion job repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from theo.application.observability import trace_repository_call
from theo.application.repositories import IngestionJobRepository

from .base_repository import BaseRepository
from .models import IngestionJob

if TYPE_CHECKING:
    from theo.application.dtos import IngestionJobDTO


class SQLAlchemyIngestionJobRepository(
    BaseRepository[IngestionJob], IngestionJobRepository
):
    """Persistence adapter for ingestion job bookkeeping."""

    def __init__(self, session: Session):
        super().__init__(session)

    def update_status(
        self,
        job_id: str,
        *,
        status: str,
        error: str | None = None,
        document_id: str | None = None,
    ) -> None:
        with trace_repository_call(
            "ingestion_job",
            "update_status",
            attributes={"job_id": job_id, "status": status},
        ) as trace:
            assignments = [
                "status = :status",
                "updated_at = :updated_at",
            ]
            params = {
                "status": status,
                "updated_at": datetime.now(UTC),
                "job_id": job_id,
            }

            if error is not None:
                assignments.append("error = :error")
                params["error"] = error
            if document_id is not None:
                assignments.append("document_id = :document_id")
                params["document_id"] = document_id

            stmt = text(
                f"""
                UPDATE ingestion_jobs
                SET {', '.join(assignments)}
                WHERE id = :job_id
                """
            )
            try:
                connection = self._session.connection()
            except RecursionError:
                trace.set_attribute("fallback", "orm_update")
                job = self.get(IngestionJob, job_id)
                trace.set_attribute("exists", job is not None)
                if job is None:
                    trace.record_result_count(0)
                    return
                job.status = status
                job.updated_at = params["updated_at"]
                if error is not None:
                    job.error = error
                if document_id is not None:
                    job.document_id = document_id
                trace.record_result_count(1)
                return

            result = connection.execute(stmt, params)
            rowcount = result.rowcount or 0
            trace.set_attribute("exists", rowcount > 0)
            trace.record_result_count(rowcount)
            if rowcount > 0:
                # Ensure ORM identity state is refreshed so callers see updated fields
                job = self._session.get(IngestionJob, job_id)
                if job is not None:
                    self._session.expire(job)

    def set_payload(self, job_id: str, payload: dict[str, Any]) -> None:
        with trace_repository_call(
            "ingestion_job",
            "set_payload",
            attributes={"job_id": job_id, "payload_keys": tuple(sorted(payload))},
        ) as trace:
            job = self.get(IngestionJob, job_id)
            trace.set_attribute("exists", job is not None)
            if job is None:
                trace.record_result_count(0)
                return
            job.payload = payload
            job.updated_at = datetime.now(UTC)
            trace.record_result_count(1)

    def merge_payload(self, job_id: str, payload: dict[str, Any]) -> None:
        with trace_repository_call(
            "ingestion_job",
            "merge_payload",
            attributes={"job_id": job_id, "payload_keys": tuple(sorted(payload))},
        ) as trace:
            job = self.get(IngestionJob, job_id)
            trace.set_attribute("exists", job is not None)
            if job is None:
                trace.record_result_count(0)
                return
            merged: dict[str, Any] = dict(job.payload or {})
            merged.update(payload)
            job.payload = merged
            job.updated_at = datetime.now(UTC)
            trace.record_result_count(1)


__all__ = ["SQLAlchemyIngestionJobRepository"]

