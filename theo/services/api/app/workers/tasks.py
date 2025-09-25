"""Celery tasks for asynchronous ingestion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from celery import Celery
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from ..core.database import get_engine
from ..core.settings import get_settings
from ..db.models import Document, IngestionJob
from ..analytics.topics import generate_topic_digest, store_topic_digest
from ..enrich import MetadataEnricher
from ..ingest.pipeline import run_pipeline_for_file, run_pipeline_for_url

logger = get_task_logger(__name__)

settings = get_settings()

celery = Celery(
    "theo-workers",
    broker=settings.redis_url,
    backend=settings.redis_url,
)


def _update_job_status(session: Session, job_id: str, *, status: str, error: str | None = None, document_id: str | None = None) -> None:
    job = session.get(IngestionJob, job_id)
    if job is None:
        return
    job.status = status
    if error is not None:
        job.error = error
    if document_id is not None:
        job.document_id = document_id
    job.updated_at = datetime.now(UTC)


@celery.task(name="tasks.process_file")
def process_file(
    doc_id: str,
    path: str,
    frontmatter: dict | None = None,
    job_id: str | None = None,
) -> None:
    """Process a file in the background via the ingestion pipeline."""

    engine = get_engine()
    with Session(engine) as session:
        if job_id:
            _update_job_status(session, job_id, status="processing")
            session.commit()
        try:
            document = run_pipeline_for_file(session, Path(path), frontmatter)
            session.commit()
            if job_id:
                _update_job_status(session, job_id, status="completed", document_id=document.id)
                session.commit()
        except Exception as exc:  # pragma: no cover - surfaced via job failure
            if job_id:
                _update_job_status(session, job_id, status="failed", error=str(exc))
                session.commit()
            raise


@celery.task(name="tasks.process_url", bind=True, max_retries=3)
def process_url(
    self,
    doc_id: str,
    url: str,
    source_type: str | None = None,
    frontmatter: dict[str, Any] | None = None,
    job_id: str | None = None,
) -> None:
    """Process a URL in the background via the ingestion pipeline."""

    engine = get_engine()

    try:
        with Session(engine) as session:
            if job_id:
                _update_job_status(session, job_id, status="processing")
                session.commit()
            document = run_pipeline_for_url(
                session,
                url,
                source_type=source_type,
                frontmatter=frontmatter,
            )
            session.commit()
            if job_id:
                _update_job_status(session, job_id, status="completed", document_id=document.id)
                session.commit()
    except Exception as exc:  # pragma: no cover - exercised indirectly via retry logic
        logger.exception(
            "Failed to process URL ingestion",
            extra={"doc_id": doc_id, "url": url, "source_type": source_type},
        )
        if job_id:
            with Session(engine) as session:
                _update_job_status(session, job_id, status="failed", error=str(exc))
                session.commit()
        retry_delay = min(2 ** self.request.retries, 60) if self.request.retries else 1
        raise self.retry(exc=exc, countdown=retry_delay)


@celery.task(name="tasks.enrich_document")
def enrich_document(document_id: str, job_id: str | None = None) -> None:
    """Lookup and persist additional bibliographic metadata."""

    engine = get_engine()
    enricher = MetadataEnricher()

    with Session(engine) as session:
        if job_id:
            _update_job_status(session, job_id, status="processing")
            session.commit()
        document = session.get(Document, document_id)
        if document is None:
            logger.warning("Document not found for enrichment", extra={"document_id": document_id})
            if job_id:
                _update_job_status(session, job_id, status="failed", error="document not found")
                session.commit()
            return

        try:
            enriched = enricher.enrich_document(session, document)
            if not enriched:
                logger.info("No enrichment data available", extra={"document_id": document_id})
            session.commit()
            if job_id:
                _update_job_status(session, job_id, status="completed", document_id=document.id)
                session.commit()
        except Exception:  # pragma: no cover - defensive logging
            session.rollback()
            logger.exception("Failed to enrich document", extra={"document_id": document_id})
            if job_id:
                with Session(engine) as retry_session:
                    _update_job_status(retry_session, job_id, status="failed", error="enrichment failed")
                    retry_session.commit()
            raise


@celery.task(name="tasks.generate_topic_digest")
def topic_digest(hours: int = 168) -> None:
    """Generate and persist a topical digest for recently ingested works."""

    engine = get_engine()
    with Session(engine) as session:
        since = datetime.now(UTC) - timedelta(hours=hours)
        digest = generate_topic_digest(session, since)
        store_topic_digest(session, digest)
        logger.info(
            "Generated topic digest",
            extra={"topics": [cluster.topic for cluster in digest.topics], "since": since.isoformat()},
        )
