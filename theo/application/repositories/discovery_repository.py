"""Repository interface for discovery persistence.

This interface defines the contract between the application and adapter layers,
using DTOs to maintain clean boundaries.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from theo.application.dtos import (
    CorpusSnapshotDTO,
    DiscoveryDTO,
    DiscoveryListFilters,
)


class DiscoveryRepository(ABC):
    """Abstract repository for discovery persistence operations."""

    @abstractmethod
    def list(self, filters: DiscoveryListFilters) -> list[DiscoveryDTO]:
        """Retrieve discoveries matching the provided filters."""
        ...

    @abstractmethod
    def get_by_id(self, discovery_id: int, user_id: str) -> DiscoveryDTO | None:
        """Retrieve a single discovery by ID and user."""
        ...

    @abstractmethod
    def create(self, discovery: DiscoveryDTO) -> DiscoveryDTO:
        """Persist a new discovery and return the saved version."""
        ...

    @abstractmethod
    def create_many(self, discoveries: Sequence[DiscoveryDTO]) -> list[DiscoveryDTO]:
        """Persist multiple discoveries in a single batch."""
        ...

    @abstractmethod
    def update(self, discovery: DiscoveryDTO) -> DiscoveryDTO:
        """Update an existing discovery."""
        ...

    @abstractmethod
    def delete_by_types(self, user_id: str, discovery_types: list[str]) -> int:
        """Delete all discoveries of specified types for a user.

        Returns the number of discoveries deleted.
        """
        ...

    @abstractmethod
    def mark_viewed(self, discovery_id: int, user_id: str) -> DiscoveryDTO:
        """Mark a discovery as viewed."""
        ...

    @abstractmethod
    def set_reaction(
        self, discovery_id: int, user_id: str, reaction: str | None
    ) -> DiscoveryDTO:
        """Set user reaction on a discovery."""
        ...

    @abstractmethod
    def create_snapshot(self, snapshot: CorpusSnapshotDTO) -> CorpusSnapshotDTO:
        """Persist a corpus snapshot."""
        ...

    @abstractmethod
    def get_recent_snapshots(
        self, user_id: str, limit: int
    ) -> list[CorpusSnapshotDTO]:
        """Retrieve recent corpus snapshots for trend analysis."""
        ...


__all__ = ["DiscoveryRepository"]
