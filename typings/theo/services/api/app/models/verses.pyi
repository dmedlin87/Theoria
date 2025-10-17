from __future__ import annotations

from datetime import datetime
from typing import Any, Literal


class VerseMention:
    passage: Any
    context_snippet: str


class VerseMentionsFilters:
    source_type: str | None
    collection: str | None
    author: str | None

    def __init__(self, **kwargs: object) -> None: ...


class VerseGraphNode:
    id: str
    label: str
    kind: Literal["verse", "mention", "commentary"]
    osis: str | None
    data: dict[str, Any] | None


class VerseGraphEdge:
    id: str
    source: str
    target: str
    kind: Literal["mention", "contradiction", "harmony", "commentary"]
    summary: str | None
    perspective: str | None
    tags: list[str] | None
    weight: float | None
    source_type: str | None
    collection: str | None
    authors: list[str] | None
    seed_id: str | None
    related_osis: str | None
    source_label: str | None


class VerseGraphFilters:
    perspectives: list[str]
    source_types: list[str]


class VerseGraphResponse:
    osis: str
    nodes: list[VerseGraphNode]
    edges: list[VerseGraphEdge]
    filters: VerseGraphFilters


class VerseTimelineBucket:
    label: str
    start: datetime
    end: datetime
    count: int
    document_ids: list[str]
    sample_passage_ids: list[str]


class VerseTimelineResponse:
    osis: str
    window: Literal["week", "month", "quarter", "year"]
    buckets: list[VerseTimelineBucket]
    total_mentions: int


__all__ = [
    "VerseMention",
    "VerseMentionsFilters",
    "VerseGraphNode",
    "VerseGraphEdge",
    "VerseGraphFilters",
    "VerseGraphResponse",
    "VerseTimelineBucket",
    "VerseTimelineResponse",
]
