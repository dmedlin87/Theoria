from __future__ import annotations

from typing import Any, Sequence


class Document:
    id: Any
    title: Any
    collection: Any
    source_type: Any
    abstract: Any
    source_url: Any
    created_at: Any


class TranscriptQuote:
    id: Any
    osis_refs: Sequence[str] | None
    quote_md: str
    source_ref: str | None
    video_id: str | None
    segment_id: str | None


__all__ = ["Document", "TranscriptQuote"]
