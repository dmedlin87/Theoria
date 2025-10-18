"""Repository abstraction for chat session persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod

from theo.application.dtos import ChatSessionDTO


class ChatSessionRepository(ABC):
    """Interface describing chat session data access patterns."""

    @abstractmethod
    def list_recent(self, limit: int) -> list[ChatSessionDTO]:
        """Return the most recently updated chat sessions up to *limit*."""


__all__ = ["ChatSessionRepository"]

