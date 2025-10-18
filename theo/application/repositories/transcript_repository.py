"""Repository abstraction for transcript segment queries."""
from __future__ import annotations

from abc import ABC, abstractmethod

from theo.application.dtos import TranscriptSegmentDTO


class TranscriptRepository(ABC):
    """Interface defining read operations for transcript segments."""

    @abstractmethod
    def search_segments(
        self,
        *,
        osis: str | None,
        video_identifier: str | None,
        limit: int,
    ) -> list[TranscriptSegmentDTO]:
        """Return transcript segments filtered by optional OSIS or video identifier."""


__all__ = ["TranscriptRepository"]
