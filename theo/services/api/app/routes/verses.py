"""Verse aggregation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..models.verses import VerseMentionsResponse
from ..retriever.verses import get_mentions_for_osis

router = APIRouter()


@router.get("/{osis}/mentions", response_model=VerseMentionsResponse)
def verse_mentions(osis: str, session: Session = Depends(get_session)) -> VerseMentionsResponse:
    """Return all passages that reference the requested OSIS verse."""

    mentions = get_mentions_for_osis(session, osis)
    return VerseMentionsResponse(osis=osis, mentions=mentions)
