"""DTOs for document domain objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DocumentSummaryDTO:
    """Lightweight document summary without passages."""

    id: str
    title: str | None
    authors: list[str] | None
    collection: str | None
    source_type: str | None
    topics: list[str] | None
    created_at: datetime


@dataclass(frozen=True)
class PassageDTO:
    """Application-layer representation of a document passage."""

    id: int
    document_id: str
    text: str | None
    page_no: int | None
    start_char: int | None
    end_char: int | None
    osis_ref: str | None
    osis_verse_ids: list[int] | None
    embedding: list[float] | None


@dataclass(frozen=True)
class DocumentDTO:
    """Complete document with passages."""

    id: str
    title: str | None
    authors: list[str] | None
    collection: str | None
    source_type: str | None
    abstract: str | None
    topics: list[str] | None
    venue: str | None
    year: int | None
    created_at: datetime
    updated_at: datetime
    passages: list[PassageDTO]
