"""Discovery domain package exposing analytics primitives."""

from .connection_engine import ConnectionDiscovery, ConnectionDiscoveryEngine
from .contradiction_engine import ContradictionDiscovery, ContradictionDiscoveryEngine
from .engine import PatternDiscoveryEngine
from .models import (
    CorpusSnapshotSummary,
    DiscoveryType,
    DocumentEmbedding,
    PatternDiscovery,
)

__all__ = [
    "ConnectionDiscovery",
    "ConnectionDiscoveryEngine",
    "ContradictionDiscovery",
    "ContradictionDiscoveryEngine",
    "CorpusSnapshotSummary",
    "DiscoveryType",
    "DocumentEmbedding",
    "PatternDiscovery",
    "PatternDiscoveryEngine",
]
