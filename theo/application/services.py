"""Application service bootstrap helpers."""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from theo.domain import Document, DocumentId

from .research import ResearchService

Session = Any


class _CommandCallable(Protocol):
    def __call__(self, document: Document) -> DocumentId: ...


class _RetireCallable(Protocol):
    def __call__(self, document_id: DocumentId) -> None: ...


class _GetCallable(Protocol):
    def __call__(self, document_id: DocumentId) -> Document | None: ...


class _ListCallable(Protocol):
    def __call__(self, *, limit: int = 20) -> list[Document]: ...


@dataclass(slots=True)
class ApplicationContainer:
    """Collection of orchestrator entry points exposed to adapters.

    The container wraps existing service functions while enabling dependency
    inversion. Framework layers should receive an instance of this container
    instead of importing deeper modules directly.
    """

    ingest_document: _CommandCallable
    retire_document: _RetireCallable
    get_document: _GetCallable
    list_documents: _ListCallable

    research_service_factory: Callable[[Session], ResearchService]

    def bind_command(self) -> Callable[[Document], DocumentId]:
        """Return a command adapter for ingestion workflows."""

        return self.ingest_document

    def bind_retire(self) -> Callable[[DocumentId], None]:
        """Return a command adapter for retirement workflows."""

        return self.retire_document

    def bind_get(self) -> Callable[[DocumentId], Document | None]:
        """Return a query adapter for fetching a single document."""

        return self.get_document

    def bind_list(self) -> Callable[[int], list[Document]]:
        """Return a query adapter for listing documents."""

        def _runner(limit: int = 20) -> list[Document]:
            return self.list_documents(limit=limit)

        return _runner

    def get_research_service(self, session: Session) -> ResearchService:
        """Return a research service bound to the provided session."""

        return self.research_service_factory(session)
