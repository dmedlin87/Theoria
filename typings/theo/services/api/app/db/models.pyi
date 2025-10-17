from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence


class Document:
    id: Any
    title: Any
    authors: list[str] | None
    doi: str | None
    source_url: str | None
    source_type: Any
    collection: Any
    pub_date: Any
    year: int | None
    venue: str | None
    abstract: Any
    topics: dict[str, Any] | list[Any] | None
    channel: str | None
    video_id: str | None
    duration_seconds: int | None
    bib_json: dict[str, Any] | None
    theological_tradition: str | None
    topic_domains: list[str] | None
    sha256: str | None
    storage_path: str | None
    enrichment_version: int | None
    provenance_score: int | None
    created_at: datetime
    updated_at: datetime
    passages: Sequence[Passage]
    annotations: Sequence[DocumentAnnotation]


class Passage:
    id: str
    document_id: str
    page_no: int | None
    t_start: float | None
    t_end: float | None
    start_char: int | None
    end_char: int | None
    osis_ref: str | None
    osis_verse_ids: list[int] | None
    osis_start_verse_id: int | None
    osis_end_verse_id: int | None
    text: str
    raw_text: str | None
    tokens: int | None
    embedding: list[float] | None
    meta: dict[str, Any] | None
    score: float | None
    document: Document
    verses: Sequence[PassageVerse]


class PassageVerse:
    passage_id: str
    verse_id: int
    passage: Passage


class DocumentAnnotation:
    id: str
    document_id: str
    body: str
    created_at: datetime
    updated_at: datetime
    document: Document


class Creator:
    id: str
    name: str
    channel: str | None
    created_at: datetime


class CreatorClaim:
    id: str
    creator_id: str
    claim_text: str
    created_at: datetime


class Video:
    id: str
    document_id: str
    video_id: str
    channel: str | None
    duration_seconds: int | None
    created_at: datetime
    document: Document


class TranscriptSegment:
    id: str
    document_id: str
    video_id: str | None
    t_start: float
    t_end: float
    text: str
    created_at: datetime
    document: Document
    verses: Sequence[TranscriptSegmentVerse]


class TranscriptSegmentVerse:
    segment_id: str
    verse_id: int
    segment: TranscriptSegment


class TranscriptQuote:
    id: Any
    osis_refs: Sequence[str] | None
    quote_md: str
    source_ref: str | None
    video_id: str | None
    segment_id: str | None
    salience: float | None


class TranscriptQuoteVerse:
    quote_id: str
    verse_id: int


class FeedbackEventAction:
    VIEW: str
    CLICK: str
    COPY: str
    LIKE: str
    DISLIKE: str
    USED_IN_ANSWER: str


class ContradictionSeed:
    id: str
    osis_a: str
    osis_b: str
    claim: str
    created_at: datetime


class HarmonySeed:
    id: str
    osis_a: str
    osis_b: str
    claim: str
    created_at: datetime


class CommentaryExcerptSeed:
    id: str
    osis_ref: str
    excerpt: str
    source: str | None
    created_at: datetime


class CaseObjectType:
    PASSAGE: str
    ANNOTATION: str
    CLAIM: str


class CaseSource:
    id: str
    created_at: datetime


class CaseObject:
    id: str
    object_type: str
    created_at: datetime


__all__ = [
    "Document",
    "Passage",
    "PassageVerse",
    "DocumentAnnotation",
    "Creator",
    "CreatorClaim",
    "Video",
    "TranscriptSegment",
    "TranscriptSegmentVerse",
    "TranscriptQuote",
    "TranscriptQuoteVerse",
    "FeedbackEventAction",
    "ContradictionSeed",
    "HarmonySeed",
    "CommentaryExcerptSeed",
    "CaseObjectType",
    "CaseSource",
    "CaseObject",
]
