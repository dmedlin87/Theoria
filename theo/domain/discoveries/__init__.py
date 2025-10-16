"""Discovery domain package exposing analytics primitives."""

from .contradiction_engine import ContradictionDiscovery, ContradictionDiscoveryEngine
from .engine import PatternDiscoveryEngine
from .models import (
    CorpusSnapshotSummary,
    DiscoveryType,
    DocumentEmbedding,
    PatternDiscovery,
)

__all__ = [
    "ContradictionDiscovery",
    "ContradictionDiscoveryEngine",
    "CorpusSnapshotSummary",
    "DiscoveryType",
    "DocumentEmbedding",
    "PatternDiscovery",
    "PatternDiscoveryEngine",
]
