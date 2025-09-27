"""Celery tasks for asynchronous ingestion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from celery import Celery
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from ..analytics.topics import (
    generate_topic_digest,
    store_topic_digest,
    upsert_digest_document,
)
from ..analytics.watchlists import (
    get_watchlist,
    iter_due_watchlists,
    run_watchlist,
)
from ..core.database import get_engine
from ..core.settings import get_settings
from ..creators.verse_perspectives import CreatorVersePerspectiveService
from ..db.models import Document, IngestionJob, Passage
from ..enrich import MetadataEnricher
from ..ingest.pipeline import run_pipeline_for_file, run_pipeline_for_url

logger = get_task_logger(__name__)

settings = get_settings()

celery = Celery(
    "theo-workers",
    broker=settings.redis_url,
    backend=settings.redis_url,
)


def _update_job_status(
    session: Session,
    job_id: str,
    *,
    status: str,
    error: str | None = None,
    document_id: str | None = None,
) -> None:
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
                _update_job_status(
                    session, job_id, status="completed", document_id=document.id
                )
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
                _update_job_status(
                    session, job_id, status="completed", document_id=document.id
                )
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
        retry_delay = min(2**self.request.retries, 60) if self.request.retries else 1
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
            logger.warning(
                "Document not found for enrichment", extra={"document_id": document_id}
            )
            if job_id:
                _update_job_status(
                    session, job_id, status="failed", error="document not found"
                )
                session.commit()
            return

        try:
            enriched = enricher.enrich_document(session, document)
            if not enriched:
                logger.info(
                    "No enrichment data available", extra={"document_id": document_id}
                )
            session.commit()
            if job_id:
                _update_job_status(
                    session, job_id, status="completed", document_id=document.id
                )
                session.commit()
        except Exception:  # pragma: no cover - defensive logging
            session.rollback()
            logger.exception(
                "Failed to enrich document", extra={"document_id": document_id}
            )
            if job_id:
                with Session(engine) as retry_session:
                    _update_job_status(
                        retry_session,
                        job_id,
                        status="failed",
                        error="enrichment failed",
                    )
                    retry_session.commit()
            raise


def _summarise_document(session: Session, document: Document) -> tuple[str, list[str]]:
    passages = (
        session.query(Passage)
        .filter(Passage.document_id == document.id)
        .order_by(
            Passage.page_no.asc(), Passage.t_start.asc(), Passage.start_char.asc()
        )
        .limit(3)
        .all()
    )
    combined = " ".join(passage.text for passage in passages if passage.text)
    if not combined:
        combined = (document.abstract or "").strip()
    text_content = combined.strip()
    summary = text_content[:380]
    if text_content and len(text_content) > 380:
        summary = f"{summary}..."
    if not summary:
        summary = f"Summary for {document.title or document.id}"
    tags: list[str] = []
    if isinstance(document.bib_json, dict):
        primary = document.bib_json.get("primary_topic")
        if isinstance(primary, str) and primary:
            tags.append(primary)
        extra = document.bib_json.get("topics")
        if isinstance(extra, list):
            tags.extend(str(item) for item in extra if item)
    return summary, tags


def _persist_summary_document(
    session: Session, source: Document, summary: str, tags: list[str]
) -> Document:
    summary_doc = Document(
        title=f"AI Summary - {source.title or source.id}",
        authors=source.authors,
        collection=source.collection,
        source_type="ai_summary",
        abstract=summary,
        topics=tags or None,
        bib_json={
            "generated_from": source.id,
            "tags": tags,
            "primary_topic": tags[0] if tags else None,
        },
    )
    session.add(summary_doc)
    session.flush()
    return summary_doc


@celery.task(name="tasks.generate_document_summary")
def generate_document_summary(document_id: str, job_id: str | None = None) -> None:
    """Create a lightweight AI summary document for the given artefact."""

    engine = get_engine()
    with Session(engine) as session:
        if job_id:
            _update_job_status(session, job_id, status="processing")
            session.commit()
        document = session.get(Document, document_id)
        if document is None:
            logger.warning(
                "Document not found for summarisation",
                extra={"document_id": document_id},
            )
            if job_id:
                _update_job_status(
                    session, job_id, status="failed", error="document not found"
                )
                session.commit()
            return

        try:
            summary, tags = _summarise_document(session, document)
            summary_doc = _persist_summary_document(session, document, summary, tags)
            session.commit()
            if job_id:
                _update_job_status(
                    session, job_id, status="completed", document_id=summary_doc.id
                )
                session.commit()
        except Exception:  # pragma: no cover - defensive logging
            session.rollback()
            logger.exception(
                "Failed to generate document summary",
                extra={"document_id": document_id},
            )
            if job_id:
                with Session(engine) as retry_session:
                    _update_job_status(
                        retry_session,
                        job_id,
                        status="failed",
                        error="summary generation failed",
                    )
                    retry_session.commit()
            raise


@celery.task(name="tasks.send_topic_digest_notification")
def send_topic_digest_notification(
    digest_document_id: str,
    recipients: list[str],
    context: dict[str, Any] | None = None,
) -> None:
    """Dispatch notifications that a topic digest is ready."""

    logger.info(
        "Dispatching topic digest notification",
        extra={
            "document_id": digest_document_id,
            "recipients": recipients,
            "context": context or {},
        },
    )

    if not recipients:
        logger.warning(
            "Skipping topic digest notification with no recipients",
            extra={"document_id": digest_document_id},
        )
        return

    webhook_url = settings.notification_webhook_url
    if not webhook_url:
        logger.warning(
            "Notification webhook URL not configured; skipping digest notification",
            extra={"document_id": digest_document_id},
        )
        return

    payload = {
        "type": "topic_digest.ready",
        "document_id": digest_document_id,
        "recipients": recipients,
        "context": context or {},
    }

    try:
        response = httpx.post(
            webhook_url,
            json=payload,
            headers=settings.notification_webhook_headers or None,
            timeout=settings.notification_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception(
            "Failed to dispatch topic digest notification",
            extra={"document_id": digest_document_id, "webhook_url": webhook_url},
        )
        raise


@celery.task(name="tasks.generate_topic_digest")
def topic_digest(
    hours: int = 168,
    *,
    since: str | None = None,
    notify: list[str] | None = None,
    job_id: str | None = None,
) -> None:
    """Generate and persist a topical digest for recently ingested works."""

    engine = get_engine()
    with Session(engine) as session:
        window_start: datetime | None = None
        if since:
            try:
                parsed = datetime.fromisoformat(since)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                window_start = parsed
            except ValueError:
                logger.warning(
                    "Invalid since value supplied to topic digest",
                    extra={"since": since},
                )

        if window_start is None:
            window_start = datetime.now(UTC) - timedelta(hours=hours)

        if job_id:
            _update_job_status(session, job_id, status="processing")
            session.commit()

        try:
            digest = generate_topic_digest(session, window_start)
            digest_document = upsert_digest_document(session, digest)
            store_topic_digest(session, digest)

            if job_id:
                _update_job_status(session, job_id, status="completed")
                session.commit()

            if notify:
                context = {
                    "generated_at": digest.generated_at.isoformat(),
                    "window_start": window_start.isoformat(),
                    "topics": [cluster.topic for cluster in digest.topics],
                }
                send_topic_digest_notification.delay(
                    digest_document.id, notify, context
                )
                logger.info(
                    "Topic digest ready for notification",
                    extra={
                        "recipients": notify,
                        "since": window_start.isoformat(),
                        "document_id": digest_document.id,
                    },
                )
            logger.info(
                "Generated topic digest",
                extra={
                    "topics": [cluster.topic for cluster in digest.topics],
                    "since": window_start.isoformat(),
                },
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            session.rollback()
            if job_id:
                _update_job_status(session, job_id, status="failed", error=str(exc))
                session.commit()
            raise


@celery.task(name="tasks.run_watchlist_alert")
def run_watchlist_alert(watchlist_id: str) -> None:
    """Execute a single watchlist evaluation run."""

    engine = get_engine()
    with Session(engine) as session:
        watchlist = get_watchlist(session, watchlist_id)
        if watchlist is None:
            logger.warning(
                "Watchlist not found for alert run",
                extra={"watchlist_id": watchlist_id},
            )
            return
        try:
            result = run_watchlist(session, watchlist, persist=True)
            logger.info(
                "Completed watchlist run",
                extra={
                    "watchlist_id": watchlist_id,
                    "matches": len(result.matches),
                    "document_ids": result.document_ids,
                },
            )
        except Exception:
            session.rollback()
            logger.exception(
                "Failed to execute watchlist run",
                extra={"watchlist_id": watchlist_id},
            )
            raise


@celery.task(name="tasks.schedule_watchlist_alerts")
def schedule_watchlist_alerts() -> None:
    """Enumerate due watchlists and queue alert runs."""

    engine = get_engine()
    scheduled = 0
    now = datetime.now(UTC)
    with Session(engine) as session:
        for watchlist in iter_due_watchlists(session, now):
            run_watchlist_alert.delay(watchlist.id)
            scheduled += 1
    logger.info(
        "Scheduled watchlist alerts",
        extra={"count": scheduled, "timestamp": now.isoformat()},
    )


@celery.task(name="tasks.refresh_creator_verse_rollups")
def refresh_creator_verse_rollups(osis_refs: list[str]) -> None:
    """Rebuild cached creator verse rollups for the supplied references."""

    if not osis_refs:
        return

    engine = get_engine()
    with Session(engine) as session:
        service = CreatorVersePerspectiveService(session)
        service.refresh_many(osis_refs)
