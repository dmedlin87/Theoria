"""Repository abstraction for embedding persistence operations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable, Sequence

from theo.application.dtos import EmbeddingUpdate, Metadata, PassageForEmbedding


class PassageEmbeddingRepository(ABC):
    """Abstract interface for persistence required by embedding rebuilds."""

    @abstractmethod
    def count_candidates(
        self,
        *,
        fast: bool,
        changed_since: datetime | None,
        ids: Sequence[str] | None,
    ) -> int:
        """Return number of passages matching the rebuild criteria."""

    @abstractmethod
    def existing_ids(self, ids: Sequence[str]) -> set[str]:
        """Return the subset of *ids* that exist in persistence."""

    @abstractmethod
    def iter_candidates(
        self,
        *,
        fast: bool,
        changed_since: datetime | None,
        ids: Sequence[str] | None,
        batch_size: int,
    ) -> Iterable[PassageForEmbedding]:
        """Yield passages requiring embedding updates in deterministic order."""

    @abstractmethod
    def update_embeddings(self, updates: Sequence[EmbeddingUpdate]) -> None:
        """Persist the provided embedding vectors for each passage."""


__all__ = [
    "EmbeddingUpdate",
    "Metadata",
    "PassageEmbeddingRepository",
    "PassageForEmbedding",
]
