"""Ingestion event emitters for downstream analytics."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Sequence

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentPersistedEvent:
    """Structured payload summarising a persisted document."""

    document_id: str
    passage_ids: list[str]
    passage_count: int
    topics: list[str]
    topic_domains: list[str]
    theological_tradition: str | None
    source_type: str | None
    metadata: dict[str, object]

    def to_payload(self) -> dict[str, object]:
        return {
            "document_id": self.document_id,
            "passage_ids": list(self.passage_ids),
            "passage_count": self.passage_count,
            "topics": list(self.topics),
            "topic_domains": list(self.topic_domains),
            "theological_tradition": self.theological_tradition,
            "source_type": self.source_type,
            "metadata": dict(self.metadata),
        }

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

    return event


__all__ = ["DocumentPersistedEvent", "emit_document_persisted_event"]

