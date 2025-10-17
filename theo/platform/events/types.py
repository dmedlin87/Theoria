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
    case_object_ids: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, object] | None = None

    @classmethod
    def from_components(
        cls,
        *,
        document_id: str,
        workflow: str,
        passage_ids: Sequence[str] | None = None,
        case_object_ids: Sequence[str] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> "DocumentIngestedEvent":
        return cls(
            document_id=document_id,
            workflow=workflow,
            passage_ids=tuple(passage_ids or ()),
            case_object_ids=tuple(dict.fromkeys(case_object_ids or ())),
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class CaseObjectsUpsertedEvent:
    """Event emitted when case builder objects are created or updated."""

    case_object_ids: tuple[str, ...]
    document_id: str | None = None

    @classmethod
    def from_ids(
        cls,
        ids: Sequence[str],
        *,
        document_id: str | None = None,
    ) -> "CaseObjectsUpsertedEvent":
        ordered = tuple(dict.fromkeys(str(identifier) for identifier in ids if identifier))
        return cls(case_object_ids=ordered, document_id=document_id)


__all__ = [
    "CaseObjectsUpsertedEvent",
    "DocumentIngestedEvent",
]
