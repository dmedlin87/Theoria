"""API routes for creator discovery and topic profiles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.settings import get_settings
from ..creators.service import (
    CreatorTopicProfileData,
    fetch_creator_topic_profile,
    search_creators,
)
from ..creators.verse_rollups import (
    CreatorVersePerspectiveService,
    VersePerspectiveCreatorData,
    VersePerspectiveQuoteData,
    VersePerspectiveSummaryData,
)
from ..models.creators import (
    CreatorSearchResponse,
    CreatorSummary,
    CreatorTopicProfile,
    CreatorTopicQuote,
    CreatorVersePerspective,
    CreatorVersePerspectiveMeta,
    CreatorVersePerspectiveQuote,
    CreatorVersePerspectiveSummary,
    CreatorVersePerspectiveVideo,
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


def _video_from_quote(quote_data: VersePerspectiveQuoteData) -> CreatorVersePerspectiveVideo | None:
    quote = quote_data.quote
    segment = quote.segment
    video = quote.video or (segment.video if segment else None)
    if not video and not segment:
        return None

    t_start = segment.t_start if segment else None
    if not video and t_start is None:
        return None

    return CreatorVersePerspectiveVideo(
        video_id=video.video_id if video else None,
        title=video.title if video else None,
        url=video.url if video else None,
        t_start=t_start,
    )


def _verse_quote_to_model(
    quote_data: VersePerspectiveQuoteData,
) -> CreatorVersePerspectiveQuote:
    quote = quote_data.quote
    segment = quote.segment
    return CreatorVersePerspectiveQuote(
        segment_id=segment.id if segment else quote.segment_id,
        quote_md=quote.quote_md,
        osis_refs=quote.osis_refs,
        source_ref=quote.source_ref,
        video=_video_from_quote(quote_data),
    )


def _creator_to_model(
    creator_data: VersePerspectiveCreatorData,
) -> CreatorVersePerspective:
    creator = creator_data.creator
    quotes = [
        _verse_quote_to_model(quote_data)
        for quote_data in creator_data.quotes
    ]
    return CreatorVersePerspective(
        creator_id=creator.id,
        creator_name=creator.name,
        stance=creator_data.stance,
        stance_counts=creator_data.stance_counts,
        confidence=creator_data.avg_confidence,
        claim_count=creator_data.claim_count,
        quotes=quotes,
    )


def _summary_to_model(
    summary: VersePerspectiveSummaryData,
) -> CreatorVersePerspectiveSummary:
    creators = [_creator_to_model(item) for item in summary.creators]
    return CreatorVersePerspectiveSummary(
        osis=summary.osis,
        total_creators=summary.total_creators,
        creators=creators,
        meta=CreatorVersePerspectiveMeta(
            range=summary.range,
            generated_at=summary.generated_at,
        ),
    )


def _ensure_feature_enabled() -> None:
    settings = get_settings()
    if not getattr(settings, "creator_verse_perspectives_enabled", False):
        raise HTTPException(status_code=404, detail="Creator verse perspectives disabled")


@router.get("/verses", response_model=CreatorVersePerspectiveSummary)
def list_creator_verse_perspectives(
    osis: str = Query(..., description="OSIS reference to summarise."),
    limit_creators: int = Query(
        default=10, ge=1, le=50, description="Maximum number of creators to include."
    ),
    limit_quotes: int = Query(
        default=3, ge=1, le=10, description="Maximum number of quotes per creator."
    ),
    session: Session = Depends(get_session),
) -> CreatorVersePerspectiveSummary:
    _ensure_feature_enabled()
    service = CreatorVersePerspectiveService(session)
    try:
        summary = service.get_summary(
            osis,
            limit_creators=limit_creators,
            limit_quotes=limit_quotes,
        )
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _summary_to_model(summary)


@router.get("/verses/{osis}", response_model=CreatorVersePerspectiveSummary)
def get_creator_verse_perspective(
    osis: str,
    limit_creators: int = Query(
        default=10, ge=1, le=50, description="Maximum number of creators to include."
    ),
    limit_quotes: int = Query(
        default=3, ge=1, le=10, description="Maximum number of quotes per creator."
    ),
    session: Session = Depends(get_session),
) -> CreatorVersePerspectiveSummary:
    _ensure_feature_enabled()
    service = CreatorVersePerspectiveService(session)
    try:
        summary = service.get_summary(
            osis,
            limit_creators=limit_creators,
            limit_quotes=limit_quotes,
        )
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _summary_to_model(summary)


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
