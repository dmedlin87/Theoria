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
from .chat import ChatSessionDTO
from .document import (
    DocumentDTO,
    DocumentSummaryDTO,
    PassageDTO,
)
from .transcript import TranscriptSegmentDTO, TranscriptVideoDTO

__all__ = [
    "CorpusSnapshotDTO",
    "ChatSessionDTO",
    "DiscoveryDTO",
    "DiscoveryListFilters",
    "DocumentDTO",
    "DocumentSummaryDTO",
    "PassageDTO",
    "TranscriptSegmentDTO",
    "TranscriptVideoDTO",
]
