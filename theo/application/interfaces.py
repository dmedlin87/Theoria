"""Interface contracts for application services."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from theo.domain import Document, DocumentId


@runtime_checkable
class CommandService(Protocol):
    """Lifecycle operations that mutate domain state."""

    def ingest_document(self, document: Document) -> DocumentId: ...
    def retire_document(self, document_id: DocumentId) -> None: ...


@runtime_checkable
class QueryService(Protocol):
    """Read-only workflows returning domain aggregates."""

    def get_document(self, document_id: DocumentId) -> Document | None: ...
    def list_documents(self, *, limit: int = 20) -> list[Document]: ...
