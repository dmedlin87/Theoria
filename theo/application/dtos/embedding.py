"""DTOs representing embedding rebuild payloads."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence


@dataclass(frozen=True)
class PassageForEmbedding:
    """Lightweight view of a passage ready for embedding generation."""

    id: str
    text: str | None
    embedding: Sequence[float] | None
    document_updated_at: datetime | None = None


@dataclass(frozen=True)
class EmbeddingUpdate:
    """Payload describing a passage embedding update operation."""

    id: str
    embedding: Sequence[float]


Metadata = Mapping[str, object]

__all__ = ["EmbeddingUpdate", "Metadata", "PassageForEmbedding"]
