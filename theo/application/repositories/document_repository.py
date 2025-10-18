"""Repository abstraction for document persistence operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from theo.application.dtos import DocumentDTO, DocumentSummaryDTO
from theo.domain.discoveries import DocumentEmbedding


class DocumentRepository(ABC):
    """Abstract interface for document data access."""

    @abstractmethod
    def list_with_embeddings(self, user_id: str) -> list[DocumentEmbedding]:
        """Return documents with averaged passage embeddings for *user_id*."""

    @abstractmethod
    def get_by_id(self, document_id: str) -> DocumentDTO | None:
        """Retrieve a single document by its identifier."""

    @abstractmethod
    def list_summaries(
        self, user_id: str, limit: int | None = None
    ) -> list[DocumentSummaryDTO]:
        """Return lightweight document summaries for the supplied *user_id*."""

    @abstractmethod
    def list_created_since(
        self, since: datetime, limit: int | None = None
    ) -> list[DocumentDTO]:
        """Return documents created on/after *since*, ordered chronologically."""


__all__ = ["DocumentRepository"]

