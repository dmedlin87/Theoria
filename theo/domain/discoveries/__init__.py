"""Discovery domain package exposing analytics primitives."""

from .anomaly_engine import AnomalyDiscovery, AnomalyDiscoveryEngine
from .connection_engine import ConnectionDiscovery, ConnectionDiscoveryEngine
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
    "ConnectionDiscovery",
    "ConnectionDiscoveryEngine",
    "ContradictionDiscovery",
    "ContradictionDiscoveryEngine",
    "AnomalyDiscovery",
    "AnomalyDiscoveryEngine",
    "GapDiscovery",
    "GapDiscoveryEngine",
    "CorpusSnapshotSummary",
    "DiscoveryType",
    "DocumentEmbedding",
    "PatternDiscovery",
    "PatternDiscoveryEngine",
]
