"""Schemas for verse aggregation responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

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


class VerseGraphNode(APIModel):
    id: str
    label: str
    kind: Literal["verse", "mention", "commentary"]
    osis: str | None = Field(default=None, description="OSIS reference represented by the node")
    data: dict[str, Any] | None = Field(
        default=None,
        description="Arbitrary metadata used to render the node or provide deep links",
    )


class VerseGraphEdge(APIModel):
    id: str
    source: str
    target: str
    kind: Literal["mention", "contradiction", "harmony", "commentary"]
    summary: str | None = Field(default=None, description="Human readable caption")
    perspective: str | None = Field(default=None, description="Perspective tag for the edge")
    tags: list[str] | None = Field(default=None, description="Topic tags associated with the edge")
    weight: float | None = Field(default=None, description="Relative weight for ranking")
    source_type: str | None = Field(default=None, description="Source type for mention edges")
    collection: str | None = Field(default=None, description="Collection label for mention edges")
    authors: list[str] | None = Field(default=None, description="Authors associated with the mention")
    seed_id: str | None = Field(default=None, description="Underlying seed identifier for reference edges")
    related_osis: str | None = Field(default=None, description="Secondary OSIS linked by the edge")
    source_label: str | None = Field(default=None, description="Display label for the edge source")


class VerseGraphFilters(APIModel):
    perspectives: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)


class VerseGraphResponse(APIModel):
    osis: str
    nodes: list[VerseGraphNode]
    edges: list[VerseGraphEdge]
    filters: VerseGraphFilters


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
