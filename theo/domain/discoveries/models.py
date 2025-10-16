"""Domain models describing discovery engine inputs and outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Mapping, Sequence


class DiscoveryType(str, Enum):
    """Discovery categories surfaced to end users."""

    PATTERN = "pattern"
    CONTRADICTION = "contradiction"
    GAP = "gap"
    CONNECTION = "connection"
    TREND = "trend"
    ANOMALY = "anomaly"


@dataclass(frozen=True)
class DocumentEmbedding:
    """Lightweight representation of a document vector and its metadata."""

    document_id: str
    title: str
    abstract: str | None
    topics: Sequence[str]
    verse_ids: Sequence[int]
    embedding: Sequence[float]
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True)
class PatternDiscovery:
    """Pattern discovery candidate ready for persistence."""

    title: str
    description: str
    confidence: float
    relevance_score: float
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CorpusSnapshotSummary:
    """Summary statistics for the analysed corpus."""

    snapshot_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    document_count: int = 0
    verse_coverage: Mapping[str, object] = field(default_factory=dict)
    dominant_themes: Mapping[str, object] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)


__all__ = [
    "DiscoveryType",
    "DocumentEmbedding",
    "PatternDiscovery",
    "CorpusSnapshotSummary",
]
