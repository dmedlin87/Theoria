"""Verse aggregation endpoints."""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.settings import get_settings
from ..models.verses import (
    VerseMentionsFilters,
    VerseMentionsResponse,
    VerseTimelineResponse,
)
from ..retriever.verses import get_mentions_for_osis, get_verse_timeline

router = APIRouter()


@router.get("/{osis}/mentions", response_model=VerseMentionsResponse)
def verse_mentions(
    osis: str,
    source_type: str | None = Query(default=None, description="Filter by source type"),
    collection: str | None = Query(default=None, description="Filter by collection"),
    author: str | None = Query(default=None, description="Filter by author"),
    session: Session = Depends(get_session),
) -> VerseMentionsResponse:
    """Return all passages that reference the requested OSIS verse."""

    filters = VerseMentionsFilters(
        source_type=source_type,
        collection=collection,
        author=author,
    )
    mentions = get_mentions_for_osis(session, osis, filters)
    return VerseMentionsResponse(osis=osis, mentions=mentions, total=len(mentions))


@router.get("/{osis}/timeline", response_model=VerseTimelineResponse)
def verse_timeline(
    osis: str,
    window: str = Query(
        default="month",
        description="Aggregation window",
        pattern="^(week|month|quarter|year)$",
    ),
    limit: int = Query(
        default=36,
        ge=1,
        le=240,
        description="Maximum number of windows to return",
    ),
    source_type: str | None = Query(default=None, description="Filter by source type"),
    collection: str | None = Query(default=None, description="Filter by collection"),
    author: str | None = Query(default=None, description="Filter by author"),
    session: Session = Depends(get_session),
) -> VerseTimelineResponse:
    """Return aggregated mention counts grouped by the requested window."""

    settings = get_settings()
    if not getattr(settings, "verse_timeline_enabled", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verse timeline is disabled")

    filters = VerseMentionsFilters(
        source_type=source_type,
        collection=collection,
        author=author,
    )
    try:
        timeline = get_verse_timeline(
            session=session,
            osis=osis,
            window=cast(Literal["week", "month", "quarter", "year"], window),
            limit=limit,
            filters=filters,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return timeline
