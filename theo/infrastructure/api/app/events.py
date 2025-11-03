"""Application event handlers wiring ingestion to downstream processes."""
from __future__ import annotations

import logging

from theo.platform.events import event_bus
from theo.platform.events.types import DocumentIngestedEvent

from .ingest.embeddings import get_embedding_service
from theo.application.facades.telemetry import log_workflow_event

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
    )


event_bus.subscribe(DocumentIngestedEvent, _handle_document_ingested_embeddings)
event_bus.subscribe(DocumentIngestedEvent, _handle_document_ingested_analytics)
