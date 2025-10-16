"""Discovery domain package exposing analytics primitives."""

from .anomaly_engine import AnomalyDiscovery, AnomalyDiscoveryEngine
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
    "AnomalyDiscovery",
    "AnomalyDiscoveryEngine",
    "CorpusSnapshotSummary",
    "DiscoveryType",
    "DocumentEmbedding",
    "PatternDiscovery",
    "PatternDiscoveryEngine",
]
