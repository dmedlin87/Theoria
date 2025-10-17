"""Graph projection contracts for synchronising domain entities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class GraphDocumentProjection:
    """Projection payload describing a document and its relationships."""

    document_id: str
    title: str | None = None
    source_type: str | None = None
    verses: tuple[str, ...] = ()
    concepts: tuple[str, ...] = ()
    topic_domains: tuple[str, ...] = ()
    theological_tradition: str | None = None


@runtime_checkable
class GraphProjector(Protocol):
    """Port used by application services to project graph entities."""

    def project_document(self, projection: GraphDocumentProjection) -> None:
        """Upsert a document node and its relationships into the graph."""

    def remove_document(self, document_id: str) -> None:
        """Remove a document node and detach its relationships from the graph."""


class NullGraphProjector:
    """No-op implementation used when graph projection is disabled."""

    __slots__ = ()

    def project_document(self, projection: GraphDocumentProjection) -> None:  # noqa: D401
        return None

    def remove_document(self, document_id: str) -> None:  # noqa: D401
        return None


__all__ = [
    "GraphDocumentProjection",
    "GraphProjector",
    "NullGraphProjector",
]
