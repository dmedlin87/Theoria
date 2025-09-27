"""Search schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import APIModel, Passage


class HybridSearchFilters(APIModel):
    collection: str | None = Field(default=None)
    author: str | None = Field(default=None)
    source_type: str | None = Field(default=None)
    theological_tradition: str | None = Field(default=None)
    topic_domain: str | None = Field(default=None)
    dataset: str | None = Field(default=None)
    variant: str | None = Field(default=None)


class HybridSearchRequest(APIModel):
    query: str | None = None
    osis: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    k: int = 10
    cursor: str | None = None
    limit: int | None = None
    mode: str = Field(
        default="results", description="Search export mode (results or mentions)"
    )


class HybridSearchResult(Passage):
    document_title: str | None = None
    snippet: str
    rank: int
    highlights: list[str] | None = None
    document_score: float | None = None
    document_rank: int | None = None


class HybridSearchResponse(APIModel):
    query: str | None = None
    osis: str | None = None
    results: list[HybridSearchResult]
    debug: dict[str, Any] | None = None
