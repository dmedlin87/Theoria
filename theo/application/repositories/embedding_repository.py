"""Protocols describing persistence behaviours for embedding rebuilds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping, Protocol, Sequence


@dataclass(slots=True)
class PassageForEmbedding:
    """Lightweight view of a passage ready for embedding generation."""

    id: str
    text: str | None
    embedding: Sequence[float] | None
    document_updated_at: datetime | None = None


@dataclass(slots=True)
class EmbeddingUpdate:
    """Payload describing a passage embedding update operation."""

    id: str
    embedding: Sequence[float]


class PassageEmbeddingRepository(Protocol):
    """Abstraction over persistence required for embedding rebuilds."""

    def count_candidates(
        self,
        *,
        fast: bool,
        changed_since: datetime | None,
        ids: Sequence[str] | None,
    ) -> int:
        """Return number of passages matching the rebuild criteria."""

    def existing_ids(self, ids: Sequence[str]) -> set[str]:
        """Return the subset of *ids* that exist in persistence."""

    def iter_candidates(
        self,
        *,
        fast: bool,
        changed_since: datetime | None,
        ids: Sequence[str] | None,
        batch_size: int,
    ) -> Iterable[PassageForEmbedding]:
        """Yield passages requiring embedding updates in deterministic order."""

    def update_embeddings(self, updates: Sequence[EmbeddingUpdate]) -> None:
        """Persist the provided embedding vectors for each passage."""


Metadata = Mapping[str, object]


__all__ = [
    "EmbeddingUpdate",
    "Metadata",
    "PassageEmbeddingRepository",
    "PassageForEmbedding",
]
