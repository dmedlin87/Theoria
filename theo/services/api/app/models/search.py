from typing import Any

from pydantic import BaseModel, Field

from .base import APIModel, Passage


class HybridSearchFilters(BaseModel):
    collection: str | None = Field(default=None, description="Optional collection filter")
    source_type: str | None = Field(default=None, description="Restrict to a source type")


class HybridSearchRequest(APIModel):
    query: str | None = None
    osis: str | None = None
    filters: HybridSearchFilters = Field(default_factory=HybridSearchFilters)
    k: int = 10


class HybridSearchResult(Passage):
    rank: int
    highlights: list[str] | None = None


class HybridSearchResponse(APIModel):
    results: list[HybridSearchResult]
    debug: dict[str, Any] | None = None
