"""Ingestion event emitters for downstream analytics."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Sequence

from theo.application.reasoner.events import DocumentPersistedEvent

LOGGER = logging.getLogger("theo.ingest.events")


def _normalise_topics(values: Iterable[str]) -> list[str]:
    topics: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        text = str(value).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        topics.append(text)
    return topics


def emit_document_persisted_event(
    *,
    document,
    passages: Sequence,
    topics: Sequence[str] | None = None,
    topic_domains: Sequence[str] | None = None,
    theological_tradition: str | None = None,
    source_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> DocumentPersistedEvent:
    """Emit a structured event after ingestion persists a document."""

    passage_ids = [passage.id for passage in passages if hasattr(passage, 'id') and passage.id is not None]
    event = DocumentPersistedEvent(
        document_id=str(document.id),
        passage_ids=passage_ids,
        passage_count=len(passage_ids),
        topics=_normalise_topics(topics or []),
        topic_domains=_normalise_topics(topic_domains or []),
        theological_tradition=(theological_tradition or None),
        source_type=(source_type or getattr(document, "source_type", None)),
        metadata={
            "title": getattr(document, "title", None),
            "collection": getattr(document, "collection", None),
            **(metadata or {}),
        },
    )

    payload = event.to_payload()
    LOGGER.info("ingest.document_persisted", extra=payload)

    _dispatch_neighborhood_event(payload)
    return event


def _dispatch_neighborhood_event(payload: dict[str, Any]) -> None:
    try:
        from ..workers import tasks as worker_tasks
    except Exception:  # pragma: no cover - worker import optional in tests
        LOGGER.debug("Workers unavailable; skipping neighborhood analytics dispatch")
        return

    task = getattr(worker_tasks, "update_neighborhood_analytics", None)
    if task is None:
        LOGGER.debug("Neighborhood analytics task not registered")
        return

    try:
        maybe_delay = getattr(task, "delay", None)
        if callable(maybe_delay):
            maybe_delay(payload)
        else:  # pragma: no cover - synchronous execution fallback
            task(payload)
    except Exception:
        LOGGER.exception("Failed to dispatch neighborhood analytics task")


__all__ = ["emit_document_persisted_event"]

