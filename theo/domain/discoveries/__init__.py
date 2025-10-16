"""Discovery domain package exposing analytics primitives."""

from .engine import PatternDiscoveryEngine
from .models import (
    CorpusSnapshotSummary,
    DiscoveryType,
    DocumentEmbedding,
    PatternDiscovery,
)

__all__ = [
    "PatternDiscoveryEngine",
    "CorpusSnapshotSummary",
    "DiscoveryType",
    "DocumentEmbedding",
    "PatternDiscovery",
]
