"""Celery tasks for asynchronous ingestion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import time
from pathlib import Path
from typing import Any, Iterable, cast

import httpx
from celery import Celery
from celery.app.task import Task as CeleryTask
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from sqlalchemy import func, literal, select, text
from sqlalchemy.orm import Session

from ..analytics.topics import (
    generate_topic_digest,
    store_topic_digest,
    upsert_digest_document,
)
from ..ai.rag import (
    build_sermon_deliverable,
    build_transcript_deliverable,
    generate_sermon_prep_outline,
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
from ..db.types import VectorType
from ..models.export import DeliverableDownload
from ..models.search import HybridSearchFilters
from ..enrich import MetadataEnricher
from ..ingest.pipeline import run_pipeline_for_file, run_pipeline_for_url

logger = get_task_logger(__name__)

settings = get_settings()

celery = Celery(
    "theo-workers",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery.conf.beat_schedule = getattr(celery.conf, "beat_schedule", {}) or {}
celery.conf.beat_schedule.setdefault(
    "refresh-hnsw-nightly",
    {
        "task": "tasks.refresh_hnsw",
        "schedule": crontab(hour="3", minute="0"),
    },
)


_DELIVERABLE_ASSET_MAP: dict[str, dict[str, tuple[str, str]]] = {
    "sermon": {
        "markdown": ("sermon.md", "text/markdown"),
        "ndjson": ("sermon.ndjson", "application/x-ndjson"),
        "csv": ("sermon.csv", "text/csv"),
        "pdf": ("sermon.pdf", "application/pdf"),
    },
    "transcript": {
        "markdown": ("transcript.md", "text/markdown"),
        "ndjson": ("transcript.ndjson", "application/x-ndjson"),
        "csv": ("transcript.csv", "text/csv"),
        "pdf": ("transcript.pdf", "application/pdf"),
    },
}


def _normalise_deliverable_formats(formats: Iterable[str]) -> list[str]:
    """Return lower-cased unique deliverable formats preserving order."""

    normalised: list[str] = []
    for fmt in formats:
        lowered = fmt.lower()
        if lowered not in normalised:
            normalised.append(lowered)
    return normalised


def _resolve_deliverable_asset(
    export_type: str, fmt: str
) -> tuple[str, str]:
    """Return the filename and media type for *fmt* under *export_type*."""

    try:
        type_map = _DELIVERABLE_ASSET_MAP[export_type]
    except KeyError as exc:  # pragma: no cover - guarded by validation
        raise ValueError(f"Unsupported deliverable type: {export_type}") from exc
    try:
        return type_map[fmt]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported format {fmt!r} for deliverable type {export_type!r}"
        ) from exc


def plan_deliverable_outputs(
    export_type: str, formats: Iterable[str], export_id: str
) -> list[DeliverableDownload]:
    """Describe the stored artifact layout for a deliverable job."""

    downloads: list[DeliverableDownload] = []
    for fmt in _normalise_deliverable_formats(formats):
        filename, media_type = _resolve_deliverable_asset(export_type, fmt)
        storage_path = f"/exports/{export_id}/{filename}"
        downloads.append(
            DeliverableDownload(
                format=fmt,
                filename=filename,
                media_type=media_type,
                storage_path=storage_path,
                public_url=storage_path,
                signed_url=storage_path,
                size_bytes=None,
            )
        )
    return downloads


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


send_topic_digest_notification_task = cast(
    CeleryTask, send_topic_digest_notification
)


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
                send_topic_digest_notification_task.delay(
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


HNSW_INDEX_NAME = "ix_passages_embedding_hnsw"
DEFAULT_SAMPLE_QUERIES = 25
DEFAULT_TOP_K = 10


def _format_vector(embedding: Iterable[float]) -> list[float]:
    return [float(component) for component in embedding]


def _rebuild_hnsw_index(engine) -> None:
    statements = [
        text(f"DROP INDEX IF EXISTS {HNSW_INDEX_NAME}"),
        text(
            "CREATE INDEX IF NOT EXISTS "
            f"{HNSW_INDEX_NAME} ON passages USING hnsw (embedding vector_l2_ops)"
        ),
        text("ANALYZE passages (embedding)"),
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(statement)


def _evaluate_hnsw_recall(
    engine, sample_queries: int = DEFAULT_SAMPLE_QUERIES, top_k: int = DEFAULT_TOP_K
) -> dict[str, Any]:
    settings = get_settings()
    metrics: dict[str, Any] = {
        "sample_size": 0,
        "top_k": top_k,
        "avg_recall": None,
        "min_recall": None,
        "max_recall": None,
        "avg_index_latency_ms": None,
        "avg_exact_latency_ms": None,
    }

    with Session(engine) as session:
        bind = session.bind
        if bind is None or bind.dialect.name != "postgresql":
            return metrics

        embeddings = (
            session.execute(
                select(Passage.embedding)
                .where(Passage.embedding.isnot(None))
                .order_by(func.random())
                .limit(sample_queries)
            )
            .scalars()
            .all()
        )

    valid_embeddings = [embedding for embedding in embeddings if embedding]
    if not valid_embeddings:
        return metrics

    recalls: list[float] = []
    index_latencies: list[float] = []
    exact_latencies: list[float] = []

    with Session(engine) as session:
        for embedding in valid_embeddings:
            vector_param = literal(
                _format_vector(embedding),
                type_=VectorType(settings.embedding_dim),
            )
            index_stmt = (
                select(Passage.id)
                .where(Passage.embedding.isnot(None))
                .order_by(func.cosine_distance(Passage.embedding, vector_param))
                .limit(top_k)
            )
            index_start = time.perf_counter()
            approx_ids = session.execute(index_stmt).scalars().all()
            index_latencies.append(time.perf_counter() - index_start)

            with session.begin():
                session.execute(text("SET LOCAL enable_indexscan = off"))
                session.execute(text("SET LOCAL enable_indexonlyscan = off"))
                session.execute(text("SET LOCAL enable_bitmapscan = off"))
                exact_start = time.perf_counter()
                exact_ids = session.execute(index_stmt).scalars().all()
                exact_latencies.append(time.perf_counter() - exact_start)

            if not exact_ids:
                continue
            overlap = len(set(approx_ids) & set(exact_ids))
            recalls.append(overlap / len(exact_ids))

    if not recalls:
        return metrics

    metrics["sample_size"] = len(recalls)
    metrics["avg_recall"] = float(sum(recalls) / len(recalls))
    metrics["min_recall"] = float(min(recalls))
    metrics["max_recall"] = float(max(recalls))
    if index_latencies:
        metrics["avg_index_latency_ms"] = float(
            sum(index_latencies) / len(index_latencies) * 1000.0
        )
    if exact_latencies:
        metrics["avg_exact_latency_ms"] = float(
            sum(exact_latencies) / len(exact_latencies) * 1000.0
        )
    return metrics


@celery.task(name="tasks.refresh_hnsw")
def refresh_hnsw(
    job_id: str | None = None,
    *,
    sample_queries: int = DEFAULT_SAMPLE_QUERIES,
    top_k: int = DEFAULT_TOP_K,
) -> dict[str, Any]:
    engine = get_engine()

    if job_id:
        with Session(engine) as session:
            _update_job_status(session, job_id, status="processing")
            session.commit()

    try:
        _rebuild_hnsw_index(engine)
        metrics = _evaluate_hnsw_recall(
            engine, sample_queries=sample_queries, top_k=top_k
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("HNSW refresh failed")
        if job_id:
            with Session(engine) as session:
                _update_job_status(session, job_id, status="failed", error=str(exc))
                session.commit()
        raise

    if job_id:
        with Session(engine) as session:
            job = session.get(IngestionJob, job_id)
            if job is not None:
                payload = dict(job.payload or {})
                payload.update({
                    "sample_queries": sample_queries,
                    "top_k": top_k,
                    "metrics": metrics,
                })
                job.payload = payload
            _update_job_status(session, job_id, status="completed")
            session.commit()

    logger.info(
        "Rebuilt pgvector HNSW index",
        extra={"metrics": metrics, "index": HNSW_INDEX_NAME},
    )
    return metrics


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


run_watchlist_alert_task = cast(CeleryTask, run_watchlist_alert)


@celery.task(name="tasks.build_deliverable")
def build_deliverable(
    *,
    export_type: str,
    formats: Iterable[str],
    export_id: str | None = None,
    topic: str | None = None,
    osis: str | None = None,
    filters: dict[str, Any] | None = None,
    model: str | None = None,
    document_id: str | None = None,
) -> dict[str, Any]:
    """Render deliverable assets, persist them, and expose download URLs."""

    engine = get_engine()
    normalised_formats = _normalise_deliverable_formats(formats)

    with Session(engine) as session:
        if export_type == "sermon":
            if not topic:
                raise ValueError("topic is required for sermon deliverables")
            filter_model = HybridSearchFilters.model_validate(filters or {})
            response = generate_sermon_prep_outline(
                session,
                topic=topic,
                osis=osis,
                filters=filter_model,
                model_name=model,
            )
            package = build_sermon_deliverable(
                response,
                formats=normalised_formats,
                filters=filter_model.model_dump(exclude_none=True),
            )
        elif export_type == "transcript":
            if not document_id:
                raise ValueError("document_id is required for transcript deliverables")
            package = build_transcript_deliverable(
                session,
                document_id,
                formats=normalised_formats,
            )
        else:
            raise ValueError(f"Unsupported deliverable type: {export_type}")

    manifest = package.manifest
    if export_id:
        manifest = manifest.model_copy(update={"export_id": export_id})
    export_id = manifest.export_id

    export_dir = settings.storage_root / "exports" / export_id
    export_dir.mkdir(parents=True, exist_ok=True)

    manifest_payload = manifest.model_dump(mode="json")
    manifest_path = export_dir / "manifest.json"
    manifest_json = manifest.model_dump_json(indent=2, exclude_none=True)
    manifest_path.write_text(manifest_json, encoding="utf-8")

    downloads: list[dict[str, Any]] = []
    for asset in package.assets:
        filename = asset.filename
        asset_path = export_dir / filename
        if isinstance(asset.content, (bytes, bytearray)):
            data = bytes(asset.content)
            asset_path.write_bytes(data)
        else:
            data = asset.content.encode("utf-8")
            asset_path.write_text(asset.content, encoding="utf-8")
        relative_path = f"/exports/{export_id}/{filename}"
        downloads.append(
            {
                "format": asset.format,
                "filename": filename,
                "media_type": asset.media_type,
                "storage_path": relative_path,
                "public_url": relative_path,
                "signed_url": relative_path,
                "size_bytes": len(data),
            }
        )

    return {
        "export_id": export_id,
        "status": "completed",
        "manifest": manifest_payload,
        "manifest_path": f"/exports/{export_id}/manifest.json",
        "assets": downloads,
    }


@celery.task(name="tasks.schedule_watchlist_alerts")
def schedule_watchlist_alerts() -> None:
    """Enumerate due watchlists and queue alert runs."""

    engine = get_engine()
    scheduled = 0
    now = datetime.now(UTC)
    with Session(engine) as session:
        for watchlist in iter_due_watchlists(session, now):
            run_watchlist_alert_task.delay(watchlist.id)
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
