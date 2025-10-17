"""Application event handlers wiring ingestion to downstream processes."""
from __future__ import annotations

import logging

from theo.platform.events import event_bus
from theo.platform.events.types import CaseObjectsUpsertedEvent, DocumentIngestedEvent

from .ingest.embeddings import get_embedding_service
from .telemetry import log_workflow_event

logger = logging.getLogger(__name__)


def _handle_document_ingested_embeddings(event: DocumentIngestedEvent) -> None:
    """Prime embedding infrastructure after successful ingestion."""

    try:
        get_embedding_service()
    except Exception:  # pragma: no cover - defensive warmup
        logger.debug("embedding service warmup failed", exc_info=True)


def _handle_document_ingested_analytics(event: DocumentIngestedEvent) -> None:
    """Record analytics breadcrumbs for ingestion workflows."""

    log_workflow_event(
        "ingest.document.persisted",
        workflow=event.workflow,
        document_id=event.document_id,
        passage_count=len(event.passage_ids),
        case_object_count=len(event.case_object_ids),
    )


def _handle_case_object_upserts(event: CaseObjectsUpsertedEvent) -> None:
    """Dispatch case object updates to the worker queue when available."""

    try:
        from .workers import tasks as worker_tasks
    except Exception:  # pragma: no cover - optional worker wiring
        logger.debug("case object worker tasks unavailable", exc_info=True)
        return

    handler = getattr(worker_tasks, "on_case_object_upsert", None)
    if handler is None:
        logger.debug("case object upsert handler missing")
        return

    for case_object_id in event.case_object_ids:
        if not case_object_id:
            continue
        try:
            maybe_delay = getattr(handler, "delay", None)
            if callable(maybe_delay):
                maybe_delay(case_object_id)
            else:
                handler(case_object_id)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception(
                "case object handler failed", extra={"case_object_id": case_object_id}
            )


event_bus.subscribe(DocumentIngestedEvent, _handle_document_ingested_embeddings)
event_bus.subscribe(DocumentIngestedEvent, _handle_document_ingested_analytics)
event_bus.subscribe(CaseObjectsUpsertedEvent, _handle_case_object_upserts)
