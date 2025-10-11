from __future__ import annotations

from typing import Sequence


class HybridSearchFilters:
    collection: str | None
    author: str | None
    source_type: str | None
    theological_tradition: str | None
    topic_domain: str | None

    def __init__(self, **kwargs: object) -> None: ...


class HybridSearchRequest:
    query: str | None
    osis: str | None
    filters: HybridSearchFilters
    k: int | None

    def __init__(
        self,
        *,
        query: str | None = ...,
        osis: str | None = ...,
        filters: HybridSearchFilters | None = ...,
        k: int | None = ...,
    ) -> None: ...


class HybridSearchResult:
    id: str
    document_id: str
    document_title: str | None
    snippet: str
    highlights: Sequence[str] | None
    osis_ref: str | None
    score: float | None
    meta: dict[str, object] | None
    start_char: int | None
    end_char: int | None


__all__ = [
    "HybridSearchFilters",
    "HybridSearchRequest",
    "HybridSearchResult",
]
