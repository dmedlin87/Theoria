"""Search schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import APIModel, Passage


class HybridSearchFilters(APIModel):
    collection: str | None = Field(default=None)
    author: str | None = Field(default=None)
    source_type: str | None = Field(default=None)


class HybridSearchRequest(APIModel):
    query: str | None = None
    osis: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    k: int = 10


class HybridSearchResult(Passage):
    document_title: str | None = None
    snippet: str
    rank: int
    highlights: list[str] | None = None


class HybridSearchResponse(APIModel):
    query: str | None = None
    osis: str | None = None
    results: list[HybridSearchResult]
    debug: dict[str, Any] | None = None
