"""Domain events consumed by the neighborhood reasoner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence


def _normalise_list(values: Sequence[Any] | None) -> list[str]:
    """Return a list of unique, non-empty string values."""

    normalised: list[str] = []
    seen: set[str] = set()
    if not values:
        return normalised
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalised.append(text)
    return normalised


@dataclass(frozen=True, slots=True)
class DocumentPersistedEvent:
    """Structured event emitted after a document and its passages persist."""

    document_id: str
    passage_ids: list[str] = field(default_factory=list)
    passage_count: int = 0
    topics: list[str] = field(default_factory=list)
    topic_domains: list[str] = field(default_factory=list)
    theological_tradition: str | None = None
    source_type: str | None = None
    emitted_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        """Serialise the event into a JSON-friendly payload."""

        payload = {
            "event": "document.persisted",
            "document_id": self.document_id,
            "passage_ids": list(self.passage_ids),
            "passage_count": int(self.passage_count),
            "topics": list(self.topics),
            "topic_domains": list(self.topic_domains),
            "theological_tradition": self.theological_tradition,
            "source_type": self.source_type,
            "emitted_at": self.emitted_at,
            "metadata": dict(self.metadata),
        }
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "DocumentPersistedEvent":
        """Reconstruct an event instance from a raw payload."""

        document_id = str(payload.get("document_id"))
        if not document_id:
            raise ValueError("document_id is required in persistence event payload")

        passage_ids = _normalise_list(payload.get("passage_ids"))
        passage_count = int(payload.get("passage_count") or len(passage_ids))
        topics = _normalise_list(payload.get("topics"))
        topic_domains = _normalise_list(payload.get("topic_domains"))

        theological_tradition = payload.get("theological_tradition")
        if theological_tradition is not None:
            theological_tradition = str(theological_tradition).strip() or None

        source_type = payload.get("source_type")
        if source_type is not None:
            source_type = str(source_type).strip() or None

        emitted_at = str(payload.get("emitted_at") or datetime.now(UTC).isoformat())

        metadata_raw = payload.get("metadata")
        metadata: dict[str, Any]
        if isinstance(metadata_raw, Mapping):
            metadata = dict(metadata_raw)
        else:
            metadata = {}

        return cls(
            document_id=document_id,
            passage_ids=passage_ids,
            passage_count=passage_count,
            topics=topics,
            topic_domains=topic_domains,
            theological_tradition=theological_tradition,
            source_type=source_type,
            emitted_at=emitted_at,
            metadata=metadata,
        )


__all__ = ["DocumentPersistedEvent"]

