"""Canonical event payloads shared across Theo subsystems."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class DocumentIngestedEvent:
    """Event emitted once a document and its passages are fully persisted."""

    document_id: str
    workflow: str
    passage_ids: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, object] | None = None

    @classmethod
    def from_components(
        cls,
        *,
        document_id: str,
        workflow: str,
        passage_ids: Sequence[str] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> "DocumentIngestedEvent":
        return cls(
            document_id=document_id,
            workflow=workflow,
            passage_ids=tuple(passage_ids or ()),
            metadata=metadata,
        )


__all__ = [
    "DocumentIngestedEvent",
]
