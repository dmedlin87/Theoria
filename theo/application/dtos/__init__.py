"""Data Transfer Objects for application layer boundaries.

DTOs decouple the application layer from adapter implementation details,
allowing the service layer to work with domain-aligned objects rather than
ORM models directly.
"""

from .discovery import (
    CorpusSnapshotDTO,
    DiscoveryDTO,
    DiscoveryListFilters,
)
from .document import (
    DocumentDTO,
    DocumentSummaryDTO,
    PassageDTO,
)

__all__ = [
    "CorpusSnapshotDTO",
    "DiscoveryDTO",
    "DiscoveryListFilters",
    "DocumentDTO",
    "DocumentSummaryDTO",
    "PassageDTO",
]
