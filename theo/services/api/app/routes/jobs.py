"""Background job management endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..db.models import Document, IngestionJob
from ..models.jobs import JobListResponse, JobQueuedResponse, JobStatus
from ..workers.tasks import enrich_document as enqueue_enrich_task
from ..workers.tasks import process_file

router = APIRouter()


def _resolve_source_file(storage_path: str | None) -> Path:
    if not storage_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document does not have stored source content",
        )

    storage_dir = Path(storage_path)
    if not storage_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stored source content is unavailable",
        )

    for candidate in sorted(storage_dir.iterdir()):
        if candidate.is_file() and candidate.name != "normalized.json":
            return candidate

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Stored source content is unavailable",
    )


def _serialize_job(job: IngestionJob) -> JobStatus:
    return JobStatus(
        id=job.id,
        document_id=job.document_id,
        job_type=job.job_type,
        status=job.status,
        task_id=job.task_id,
        error=job.error,
        payload=job.payload,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/", response_model=JobListResponse)
def list_jobs(
    limit: int = Query(default=25, ge=1, le=200),
    document_id: str | None = Query(default=None, description="Filter jobs by document."),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by job status."),
    session: Session = Depends(get_session),
) -> JobListResponse:
    stmt = select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(limit)
    if document_id:
        stmt = stmt.where(IngestionJob.document_id == document_id)
    if status_filter:
        stmt = stmt.where(IngestionJob.status == status_filter)
    jobs = session.execute(stmt).scalars().all()
    return JobListResponse(jobs=[_serialize_job(job) for job in jobs])


@router.get("/{job_id}", response_model=JobStatus)
def get_job(job_id: str, session: Session = Depends(get_session)) -> JobStatus:
    job = session.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _serialize_job(job)


@router.post(
    "/reparse/{document_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobQueuedResponse,
)
def enqueue_reparse_job(
    document_id: str,
    session: Session = Depends(get_session),
) -> JobStatus:
    """Queue a background reparse job for an existing document."""

    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    source_file = _resolve_source_file(document.storage_path)

    job = IngestionJob(
        document_id=document.id,
        job_type="reparse",
        status="queued",
        payload={"source_path": str(source_file)},
    )
    session.add(job)
    session.commit()

    delay_callable = process_file.delay
    try:
        async_result = delay_callable(document.id, str(source_file), None, job.id)
    except TypeError:
        async_result = delay_callable(document.id, str(source_file), None)
    task_id = getattr(async_result, "id", None)
    if task_id:
        job.task_id = task_id
        session.add(job)
        session.commit()

    session.refresh(job)
    return JobQueuedResponse(document_id=document.id, status=job.status)


@router.post("/enrich/{document_id}", status_code=status.HTTP_202_ACCEPTED, response_model=JobStatus)
def enqueue_enrichment_job(
    document_id: str,
    session: Session = Depends(get_session),
) -> JobStatus:
    """Queue a metadata enrichment job for an existing document."""

    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    job = IngestionJob(
        document_id=document.id,
        job_type="enrich",
        status="queued",
    )
    session.add(job)
    session.commit()

    async_result = enqueue_enrich_task.delay(document.id, job.id)
    task_id = getattr(async_result, "id", None)
    if task_id:
        job.task_id = task_id
        session.add(job)
        session.commit()

    session.refresh(job)
    return _serialize_job(job)
