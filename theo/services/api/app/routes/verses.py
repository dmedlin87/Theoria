from fastapi import APIRouter

from ..models.verses import VerseMentionsResponse
from ..retriever.verses import get_mentions_for_osis

router = APIRouter()


@router.get("/{osis}/mentions", response_model=VerseMentionsResponse)
async def verse_mentions(osis: str):
    """Return all passages that reference the requested OSIS verse."""
    mentions = get_mentions_for_osis(osis)
    return VerseMentionsResponse(osis=osis, mentions=mentions)
