"""Background job management endpoints."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from typing import Any, NotRequired, TypedDict, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..db.models import Document, IngestionJob
from ..models.jobs import (
    HNSWRefreshJobRequest,
    JobEnqueueRequest,
    JobEnqueueResponse,
    JobListResponse,
    JobQueuedResponse,
    JobStatus,
    JSONDict,
    SummaryJobRequest,
    TopicDigestJobRequest,
)
from ..workers.tasks import (
    celery,
    enrich_document as enqueue_enrich_task,
    generate_document_summary as summary_task,
    process_file,
    refresh_hnsw as refresh_hnsw_task,
    topic_digest as topic_digest_task,
)

router = APIRouter()

IDEMPOTENCY_TTL = timedelta(minutes=10)


class TopicDigestTaskArgs(TypedDict):
    """Keyword arguments passed to the topic digest Celery task."""

    job_id: str
    since: NotRequired[str]
    notify: NotRequired[list[str]]


class TopicDigestJobPayload(TypedDict, total=False):
    """Stored payload associated with a topic digest job."""

    since: str
    notify: list[str]


class EnqueueJobPayload(TypedDict, total=False):
    """JSON payload stored for scheduled deterministic tasks."""

    args: JSONDict
    schedule_at: str


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
    document_id: str | None = Query(
        default=None, description="Filter jobs by document."
    ),
    status_filter: str | None = Query(
        default=None, alias="status", description="Filter by job status."
    ),
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return _serialize_job(job)


@router.post(
    "/reparse/{document_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobQueuedResponse,
)
def enqueue_reparse_job(
    document_id: str,
    session: Session = Depends(get_session),
) -> JobQueuedResponse:
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


@router.post(
    "/enrich/{document_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobStatus,
)
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


@router.post(
    "/refresh-hnsw",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobStatus,
)
def enqueue_refresh_hnsw_job(
    request: HNSWRefreshJobRequest, session: Session = Depends(get_session)
) -> JobStatus:
    """Queue a pgvector HNSW refresh and recall evaluation."""

    job = IngestionJob(
        job_type="refresh_hnsw",
        status="queued",
        payload={
            "sample_queries": request.sample_queries,
            "top_k": request.top_k,
        },
    )
    session.add(job)
    session.commit()

    delay_callable = refresh_hnsw_task.delay
    try:
        async_result = delay_callable(
            job.id,
            sample_queries=request.sample_queries,
            top_k=request.top_k,
        )
    except TypeError:  # pragma: no cover - celery stubs in tests
        async_result = delay_callable(job.id)
    task_id = getattr(async_result, "id", None)
    if task_id:
        job.task_id = task_id
        session.add(job)
        session.commit()

    session.refresh(job)
    return _serialize_job(job)


@router.post(
    "/summaries",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobStatus,
)
def enqueue_summary_job(
    payload: SummaryJobRequest, session: Session = Depends(get_session)
) -> JobStatus:
    """Queue a summary-generation job for an existing document."""

    document = session.get(Document, payload.document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    job = IngestionJob(
        document_id=document.id,
        job_type="summary",
        status="queued",
        payload={"source_document_id": document.id},
    )
    session.add(job)
    session.commit()

    async_result = summary_task.delay(document.id, job.id)
    task_id = getattr(async_result, "id", None)
    if task_id:
        job.task_id = task_id
        session.add(job)
        session.commit()

    session.refresh(job)
    return _serialize_job(job)


@router.post(
    "/topic_digest",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobStatus,
)
def enqueue_topic_digest_job(
    payload: TopicDigestJobRequest,
    session: Session = Depends(get_session),
) -> JobStatus:
    """Queue a background job that generates the topical activity digest."""

    notify = payload.notify or []
    since = payload.since

    job_payload: TopicDigestJobPayload = {}
    if since:
        job_payload["since"] = since.isoformat()
    if notify:
        job_payload["notify"] = notify

    job = IngestionJob(
        job_type="topic_digest",
        status="queued",
        payload=job_payload or None,
    )
    session.add(job)
    session.commit()

    kwargs: TopicDigestTaskArgs = {"job_id": job.id}
    if since:
        kwargs["since"] = since.isoformat()
    if notify:
        kwargs["notify"] = notify

    async_result = topic_digest_task.delay(**kwargs)
    task_id = getattr(async_result, "id", None)
    if task_id:
        job.task_id = task_id
        session.add(job)
        session.commit()

    session.refresh(job)
    return _serialize_job(job)


def _normalize_args(args: JSONDict | None) -> JSONDict:
    return args.copy() if args else {}


def _hash_args(args: JSONDict) -> str:
    encoded = json.dumps(
        args, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


@router.post(
    "/enqueue", response_model=JobEnqueueResponse, status_code=status.HTTP_202_ACCEPTED
)
def enqueue_job(
    payload: JobEnqueueRequest,
    session: Session = Depends(get_session),
) -> JobEnqueueResponse:
    """Enqueue a task with deterministic, idempotent responses."""

    args = _normalize_args(payload.args)
    args_hash = _hash_args(args)
    now = datetime.now(UTC)
    cutoff = now - IDEMPOTENCY_TTL

    existing = (
        session.query(IngestionJob)
        .filter(
            IngestionJob.job_type == payload.task,
            IngestionJob.args_hash == args_hash,
            IngestionJob.created_at >= cutoff,
        )
        .order_by(IngestionJob.created_at.desc())
        .first()
    )
    if existing is not None:
        return JobEnqueueResponse(
            job_id=existing.id,
            task=existing.job_type,
            args_hash=args_hash,
            queued_at=existing.created_at,
            schedule_at=existing.scheduled_at,
            status_url=f"/jobs/{existing.id}",
        )

    schedule_at = payload.schedule_at
    if schedule_at is not None and schedule_at.tzinfo is None:
        schedule_at = schedule_at.replace(tzinfo=UTC)

    stored_payload: EnqueueJobPayload = {"args": args} if args else {}
    if schedule_at:
        stored_payload["schedule_at"] = schedule_at.isoformat()

    job = IngestionJob(
        job_type=payload.task,
        status="queued",
        payload=stored_payload or None,
        args_hash=args_hash,
        scheduled_at=schedule_at,
    )
    session.add(job)
    session.flush()

    send_kwargs: dict[str, Any] = {
        key: cast(Any, value) for key, value in args.items()
    }
    eta = schedule_at
    result = celery.send_task(payload.task, kwargs=send_kwargs, eta=eta)
    task_id = getattr(result, "id", None)
    if task_id:
        job.task_id = task_id

    session.commit()
    session.refresh(job)

    return JobEnqueueResponse(
        job_id=job.id,
        task=job.job_type,
        args_hash=args_hash,
        queued_at=job.created_at,
        schedule_at=job.scheduled_at,
        status_url=f"/jobs/{job.id}",
    )
