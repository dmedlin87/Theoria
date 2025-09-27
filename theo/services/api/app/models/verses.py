"""Schemas for verse aggregation responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .base import APIModel, Passage


class VerseMention(APIModel):
    passage: Passage
    context_snippet: str = Field(description="Relevant text around the verse reference")


class VerseMentionsFilters(APIModel):
    source_type: str | None = None
    collection: str | None = None
    author: str | None = None


class VerseMentionsResponse(APIModel):
    osis: str
    mentions: list[VerseMention]
    total: int


class VerseTimelineBucket(APIModel):
    label: str = Field(description="Human-readable window identifier")
    start: datetime = Field(description="Inclusive start of the window")
    end: datetime = Field(description="Exclusive end of the window")
    count: int = Field(description="Number of mentions in the window")
    document_ids: list[str] = Field(
        default_factory=list,
        description="Unique document identifiers represented in the bucket",
    )
    sample_passage_ids: list[str] = Field(
        default_factory=list,
        description="Sample passage identifiers from the bucket",
    )


class VerseTimelineResponse(APIModel):
    osis: str
    window: Literal["week", "month", "quarter", "year"]
    buckets: list[VerseTimelineBucket]
    total_mentions: int
