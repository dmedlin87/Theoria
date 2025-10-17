from __future__ import annotations

from typing import Sequence


class HybridSearchFilters:
    collection: str | None
    author: str | None
    source_type: str | None
    theological_tradition: str | None
    topic_domain: str | None

    def __init__(self, **kwargs: object) -> None: ...
    def model_dump(self, **kwargs: object) -> dict[str, object]: ...


class HybridSearchRequest:
    query: str | None
    osis: str | None
    filters: HybridSearchFilters
    k: int | None
    cursor: str | None
    limit: int | None
    mode: str

    def __init__(
        self,
        *,
        query: str | None = ...,
        osis: str | None = ...,
        filters: HybridSearchFilters | None = ...,
        k: int | None = ...,
        cursor: str | None = ...,
        limit: int | None = ...,
        mode: str = ...,
    ) -> None: ...


class HybridSearchResult:
    id: str
    document_id: str
    text: str
    raw_text: str | None
    document_title: str | None
    snippet: str
    rank: int
    highlights: Sequence[str] | None
    osis_ref: str | None
    page_no: int | None
    t_start: float | None
    t_end: float | None
    score: float | None
    document_score: float | None
    document_rank: int | None
    lexical_score: float | None
    vector_score: float | None
    osis_distance: float | None
    meta: dict[str, object] | None
    start_char: int | None
    end_char: int | None

    def model_dump(self, **kwargs: object) -> dict[str, object]: ...


__all__ = [
    "HybridSearchFilters",
    "HybridSearchRequest",
    "HybridSearchResult",
]
