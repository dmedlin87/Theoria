"""Interface contracts for application services."""
from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

from theo.domain import Document, DocumentId

_EntityT = TypeVar("_EntityT")


class SessionProtocol(Protocol):
    """Subset of unit-of-work behaviours required by application services."""

    def get(
        self, entity: type[_EntityT], ident: Any, /, **kwargs: Any
    ) -> _EntityT | None: ...

    def add(self, instance: object, /, **kwargs: Any) -> None: ...

    def commit(self) -> None: ...


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


__all__ = [
    "CommandService",
    "QueryService",
    "SessionProtocol",
]
@runtime_checkable
class LanguageModelClientProtocol(Protocol):
    """Protocol describing the behaviour exposed by language model clients."""

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 800,
        cache_key: str | None = None,
    ) -> str: ...
