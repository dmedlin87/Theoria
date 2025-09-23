"""Celery tasks for asynchronous ingestion."""

from __future__ import annotations

from pathlib import Path

from celery import Celery
from sqlalchemy.orm import Session

from ..core.database import get_engine
from ..ingest.pipeline import run_pipeline_for_file

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


@celery.task(name="tasks.process_url")
def process_url(doc_id: str, url: str, source_type: str | None = None) -> None:
    raise NotImplementedError("URL ingestion worker not yet implemented")
