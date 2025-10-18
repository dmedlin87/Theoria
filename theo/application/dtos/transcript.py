"""Transcript-specific data transfer objects."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptVideoDTO:
    """Application-layer representation of a transcript's video metadata."""

    id: str | None
    video_id: str | None
    title: str | None
    url: str | None


@dataclass(frozen=True)
class TranscriptSegmentDTO:
    """Immutable transcript segment representation for application consumers."""

    id: str
    document_id: str | None
    text: str | None
    primary_osis: str | None
    osis_refs: tuple[str, ...]
    osis_verse_ids: tuple[int, ...]
    t_start: float | None
    t_end: float | None
    video: TranscriptVideoDTO | None
