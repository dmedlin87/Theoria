from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DummyDocument:
    id: str
    title: str | None = None
    source_type: str | None = None
    collection: str | None = None
    authors: list[str] | None = None
    doi: str | None = None
    venue: str | None = None
    year: int | None = None
    source_url: str | None = None
    topics: Any | None = None
    theological_tradition: str | None = None
    topic_domains: list[str] | None = None
    enrichment_version: int | None = None
    provenance_score: float | None = None
    bib_json: dict[str, Any] | None = None


@dataclass
class DummyPassage:
    id: str
    document_id: str
    text: str
    raw_text: str | None = None
    osis_ref: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    page_no: int | None = None
    t_start: float | None = None
    t_end: float | None = None
    score: float | None = None
    meta: dict[str, Any] | None = field(default_factory=dict)
    lexeme: Any | None = None

    osis_start_verse_id: int | None = None
    osis_end_verse_id: int | None = None
    osis_verse_ids: list[int] | None = None
