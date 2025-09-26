"""API routes for creator discovery and topic profiles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..creators.service import (
    CreatorTopicProfileData,
    fetch_creator_topic_profile,
    search_creators,
)
from ..models.creators import (
    CreatorSearchResponse,
    CreatorSummary,
    CreatorTopicProfile,
    CreatorTopicQuote,
)

router = APIRouter()


@router.get("/search", response_model=CreatorSearchResponse)
def search_creators_route(
    q: str | None = Query(
        default=None, alias="query", description="Filter creators by name."
    ),
    limit: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> CreatorSearchResponse:
    creators = search_creators(session, query=q, limit=limit)
    results = [
        CreatorSummary(
            id=creator.id, name=creator.name, channel=creator.channel, tags=creator.tags
        )
        for creator in creators
    ]
    return CreatorSearchResponse(query=q, results=results)


def _quote_from_data(
    data: CreatorTopicProfileData, *, limit: int
) -> list[CreatorTopicQuote]:
    quotes: list[CreatorTopicQuote] = []
    for quote in data.quotes[:limit]:
        segment = quote.segment
        video = quote.video or (segment.video if segment else None)
        quotes.append(
            CreatorTopicQuote(
                segment_id=segment.id if segment else quote.segment_id or "",
                quote=quote.quote_md,
                osis_refs=quote.osis_refs,
                source_ref=quote.source_ref,
                video_id=video.video_id if video else None,
                video_title=video.title if video else None,
                video_url=video.url if video else None,
                t_start=segment.t_start if segment else None,
                t_end=segment.t_end if segment else None,
            )
        )
    return quotes


@router.get("/{creator_id}/topics", response_model=CreatorTopicProfile)
def get_creator_topic_profile(
    creator_id: str,
    topic: str = Query(..., description="Topic to summarize for the creator."),
    limit: int = Query(
        default=5, ge=1, le=20, description="Maximum number of quotes to return."
    ),
    session: Session = Depends(get_session),
) -> CreatorTopicProfile:
    try:
        profile = fetch_creator_topic_profile(
            session, creator_id=creator_id, topic=topic, limit=limit
        )
    except LookupError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=404, detail="Creator not found") from exc

    quotes = _quote_from_data(profile, limit=limit)
    claim_summaries = [claim.claim_md for claim in profile.claims]
    return CreatorTopicProfile(
        creator_id=profile.creator.id,
        creator_name=profile.creator.name,
        topic=profile.topic,
        stance=profile.stance,
        confidence=profile.confidence,
        quotes=quotes,
        claim_summaries=claim_summaries,
        total_claims=len(profile.claims),
    )
