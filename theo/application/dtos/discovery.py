"""DTOs for discovery domain objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DiscoveryDTO:
    """Application-layer representation of a discovery.
    
    Decouples service layer from ORM model implementation.
    """
    
    id: int
    user_id: str
    discovery_type: str
    title: str
    description: str | None
    confidence: float
    relevance_score: float
    viewed: bool
    user_reaction: str | None
    created_at: datetime
    metadata: dict[str, object]


@dataclass(frozen=True)
class DiscoveryListFilters:
    """Filters for querying discoveries."""
    
    user_id: str
    discovery_type: str | None = None
    viewed: bool | None = None
    min_confidence: float | None = None
    limit: int | None = None
    offset: int | None = None


@dataclass(frozen=True)
class CorpusSnapshotDTO:
    """Application-layer representation of a corpus snapshot."""
    
    id: int
    user_id: str
    snapshot_date: datetime
    document_count: int
    verse_coverage: dict[str, object]
    dominant_themes: dict[str, object]
    metadata: dict[str, object]
