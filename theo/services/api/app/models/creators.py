"""Pydantic schemas for creator profile endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import List

from .base import APIModel


class CreatorSummary(APIModel):
    id: str
    name: str
    channel: str | None = None
    tags: List[str] | None = None


class CreatorSearchResponse(APIModel):
    query: str | None
    results: List[CreatorSummary]


class CreatorTopicQuote(APIModel):
    segment_id: str
    quote: str
    osis_refs: List[str] | None = None
    source_ref: str | None = None
    video_id: str | None = None
    video_title: str | None = None
    video_url: str | None = None
    t_start: float | None = None
    t_end: float | None = None


class CreatorTopicProfile(APIModel):
    creator_id: str
    creator_name: str
    topic: str
    stance: str | None = None
    confidence: float | None = None
    quotes: List[CreatorTopicQuote]
    claim_summaries: List[str]
    total_claims: int


class CreatorVersePerspectiveVideo(APIModel):
    video_id: str | None = None
    title: str | None = None
    url: str | None = None
    t_start: float | None = None


class CreatorVersePerspectiveQuote(APIModel):
    segment_id: str | None = None
    quote_md: str
    osis_refs: List[str] | None = None
    source_ref: str | None = None
    video: CreatorVersePerspectiveVideo | None = None


class CreatorVersePerspective(APIModel):
    creator_id: str
    creator_name: str
    stance: str | None = None
    stance_counts: dict[str, int]
    confidence: float | None = None
    claim_count: int
    quotes: List[CreatorVersePerspectiveQuote]


class CreatorVersePerspectiveMeta(APIModel):
    range: str
    generated_at: datetime


class CreatorVersePerspectiveSummary(APIModel):
    osis: str
    total_creators: int
    creators: List[CreatorVersePerspective]
    meta: CreatorVersePerspectiveMeta
