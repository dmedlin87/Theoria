from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from theo.services.api.app.models.verses import VerseMentionsFilters


class VerseTimelineBucket:
    label: str
    start: datetime
    end: datetime
    count: int
    document_ids: Sequence[str]


class VerseTimeline:
    buckets: Sequence[VerseTimelineBucket]
    total_mentions: int


def get_verse_timeline(
    session: Session,
    osis: str,
    *,
    window: Literal["week", "month", "quarter", "year"],
    limit: int,
    filters: VerseMentionsFilters | None = ...,
) -> VerseTimeline: ...


__all__ = ["VerseTimeline", "VerseTimelineBucket", "get_verse_timeline"]
