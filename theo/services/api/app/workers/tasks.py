"""Celery tasks for asynchronous ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from celery import Celery
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from ..core.database import get_engine
from ..core.settings import get_settings
from ..db.models import Document
from ..enrich import MetadataEnricher
from ..ingest.pipeline import run_pipeline_for_file, run_pipeline_for_url

logger = get_task_logger(__name__)

settings = get_settings()

celery = Celery(
    "theo-workers",
    broker=settings.redis_url,
    backend=settings.redis_url,
)


@celery.task(name="tasks.process_file")
def process_file(doc_id: str, path: str, frontmatter: dict | None = None) -> None:
    """Process a file in the background via the ingestion pipeline."""

    engine = get_engine()
    with Session(engine) as session:
        run_pipeline_for_file(session, Path(path), frontmatter)


@celery.task(name="tasks.process_url", bind=True, max_retries=3)
def process_url(
    self,
    doc_id: str,
    url: str,
    source_type: str | None = None,
    frontmatter: dict[str, Any] | None = None,
) -> None:
    """Process a URL in the background via the ingestion pipeline."""

    engine = get_engine()

    try:
        with Session(engine) as session:
            run_pipeline_for_url(
                session,
                url,
                source_type=source_type,
                frontmatter=frontmatter,
            )
    except Exception as exc:  # pragma: no cover - exercised indirectly via retry logic
        logger.exception(
            "Failed to process URL ingestion",
            extra={"doc_id": doc_id, "url": url, "source_type": source_type},
        )
        retry_delay = min(2 ** self.request.retries, 60) if self.request.retries else 1
        raise self.retry(exc=exc, countdown=retry_delay)


@celery.task(name="tasks.enrich_document")
def enrich_document(document_id: str) -> None:
    """Lookup and persist additional bibliographic metadata."""

    engine = get_engine()
    enricher = MetadataEnricher()

    with Session(engine) as session:
        document = session.get(Document, document_id)
        if document is None:
            logger.warning("Document not found for enrichment", extra={"document_id": document_id})
            return

        try:
            enriched = enricher.enrich_document(session, document)
            if not enriched:
                logger.info("No enrichment data available", extra={"document_id": document_id})
        except Exception:  # pragma: no cover - defensive logging
            session.rollback()
            logger.exception("Failed to enrich document", extra={"document_id": document_id})
            raise
