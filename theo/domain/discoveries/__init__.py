"""Discovery domain package exposing analytics primitives."""

from .contradiction_engine import ContradictionDiscovery, ContradictionDiscoveryEngine
from .gap_engine import GapDiscovery, GapDiscoveryEngine
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
    "GapDiscovery",
    "GapDiscoveryEngine",
    "CorpusSnapshotSummary",
    "DiscoveryType",
    "DocumentEmbedding",
    "PatternDiscovery",
    "PatternDiscoveryEngine",
]
