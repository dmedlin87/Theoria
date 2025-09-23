"""Schemas for verse aggregation responses."""

from __future__ import annotations

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
