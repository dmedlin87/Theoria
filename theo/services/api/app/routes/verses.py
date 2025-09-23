"""Verse aggregation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..models.verses import VerseMentionsFilters, VerseMentionsResponse
from ..retriever.verses import get_mentions_for_osis

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
