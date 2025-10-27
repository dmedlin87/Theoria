"""Routes exposing transcript search capabilities."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from theo.adapters.persistence.transcript_repository import (
    SQLAlchemyTranscriptRepository,
)
from theo.application.facades.database import get_session

from ..models.transcripts import TranscriptSearchResponse, TranscriptSegmentModel
from ..transcripts.service import (
    build_source_ref,
    canonical_primary_osis,
    search_transcript_segments,
)

router = APIRouter()


@router.get("/search", response_model=TranscriptSearchResponse)
def search_transcripts(
    osis: str | None = Query(default=None, description="Filter by OSIS reference."),
    video: str | None = Query(
        default=None, description="Filter by video identifier or internal id."
    ),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> TranscriptSearchResponse:
    repository = SQLAlchemyTranscriptRepository(session)
    segments = search_transcript_segments(
        repository, osis=osis, video_identifier=video, limit=limit
    )
    models: list[TranscriptSegmentModel] = []
    for segment in segments:
        video_model = segment.video
        source_ref = build_source_ref(video_model, segment.t_start)
        models.append(
            TranscriptSegmentModel(
                id=segment.id,
                document_id=segment.document_id,
                video_id=video_model.video_id if video_model else None,
                text=segment.text,
                primary_osis=canonical_primary_osis(segment),
                osis_refs=segment.osis_refs,
                t_start=segment.t_start,
                t_end=segment.t_end,
                source_ref=source_ref,
                video_title=video_model.title if video_model else None,
                video_url=video_model.url if video_model else None,
            )
        )
    return TranscriptSearchResponse(
        osis=osis, video=video, total=len(models), segments=models
    )
