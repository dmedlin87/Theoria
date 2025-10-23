"""Discovery domain package exposing analytics primitives."""

from .anomaly_engine import AnomalyDiscovery, AnomalyDiscoveryEngine
from .connection_engine import ConnectionDiscovery, ConnectionDiscoveryEngine
from .contradiction_engine import ContradictionDiscovery, ContradictionDiscoveryEngine
from .engine import PatternDiscoveryEngine
from .gap_engine import GapDiscovery, GapDiscoveryEngine
from .models import (
    CorpusSnapshotSummary,
    DiscoveryType,
    DocumentEmbedding,
    PatternDiscovery,
)
from .trend_engine import TrendDiscovery, TrendDiscoveryEngine

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
    "TrendDiscovery",
    "TrendDiscoveryEngine",
]
