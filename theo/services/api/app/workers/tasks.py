"""Celery task queue definitions."""

from celery import Celery
from fastapi import BackgroundTasks, UploadFile

from ..models.documents import Document

celery = Celery(
    "theo-workers",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
)


@celery.task(name="tasks.process_file")
def process_file(doc_id: str, path: str, frontmatter: dict | None = None) -> None:
    """Placeholder pipeline entrypoint for file ingestion."""


@celery.task(name="tasks.process_url")
def process_url(doc_id: str, url: str, source_type: str | None = None) -> None:
    """Placeholder pipeline entrypoint for URL ingestion."""


def queue_file_ingest(background: BackgroundTasks, file: UploadFile) -> Document:
    document = Document(source_type="upload")
    background.add_task(process_file.delay, str(document.document_id), file.filename, None)
    return document


def queue_url_ingest(background: BackgroundTasks, url: str) -> Document:
    document = Document(source_type="url")
    background.add_task(process_url.delay, str(document.document_id), url, None)
    return document
