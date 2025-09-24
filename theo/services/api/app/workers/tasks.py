"""Celery tasks for asynchronous ingestion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from celery import Celery
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from ..core.database import get_engine
from ..ingest.pipeline import run_pipeline_for_file, run_pipeline_for_url

logger = get_task_logger(__name__)

celery = Celery(
    "theo-workers",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
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
