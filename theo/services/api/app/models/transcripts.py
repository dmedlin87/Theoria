"""Transcript search response models."""

from __future__ import annotations

from typing import List

from .base import APIModel


class TranscriptSegmentModel(APIModel):
    id: str
    document_id: str | None = None
    video_id: str | None = None
    text: str
    primary_osis: str | None = None
    osis_refs: List[str] | None = None
    t_start: float | None = None
    t_end: float | None = None
    source_ref: str | None = None
    video_title: str | None = None
    video_url: str | None = None


class TranscriptSearchResponse(APIModel):
    osis: str | None = None
    video: str | None = None
    total: int
    segments: List[TranscriptSegmentModel]
