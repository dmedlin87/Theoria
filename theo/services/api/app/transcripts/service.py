"""Query helpers for transcript segments."""

from __future__ import annotations

import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db.models import TranscriptSegment, Video
from ..ingest.osis import expand_osis_reference

LOGGER = logging.getLogger(__name__)


def _matches_osis(segment: TranscriptSegment, osis: str) -> bool:
    """Return True when *segment* overlaps the requested OSIS reference."""

    references: list[str] = []
    if segment.primary_osis:
        references.append(segment.primary_osis)
    if segment.osis_refs:
        references.extend(ref for ref in segment.osis_refs if ref)

    try:
        target_ids = expand_osis_reference(osis)
    except Exception as exc:  # pragma: no cover - defensive against malformed input
        LOGGER.exception("Failed to expand OSIS reference %s", osis, exc_info=exc)
        return False
    if not target_ids:
        return False

    for reference in references:
        try:
            if expand_osis_reference(reference) & target_ids:
                return True
        except Exception as exc:  # pragma: no cover - defensive against malformed data
            LOGGER.exception(
                "Failed to expand OSIS reference %s for transcript match", reference, exc_info=exc
            )
            continue
    return False


def build_source_ref(video: Video | None, t_start: float | None) -> str | None:
    """Create a timestamped reference (e.g. youtube:ID#t=MM:SS)."""

    if video is None or video.video_id is None or t_start is None:
        return None
    prefix = "video"
    if video.url:
        lowered = video.url.lower()
        if "youtube" in lowered or "youtu.be" in lowered:
            prefix = "youtube"
        elif "vimeo" in lowered:
            prefix = "vimeo"
    seconds = max(0, int(t_start))
    minutes, remaining = divmod(seconds, 60)
    return f"{prefix}:{video.video_id}#t={minutes:02d}:{remaining:02d}"


def search_transcript_segments(
    session: Session,
    *,
    osis: str | None,
    video_identifier: str | None,
    limit: int,
) -> list[TranscriptSegment]:
    """Return transcript segments filtered by OSIS and/or video identifier."""

    query = session.query(TranscriptSegment).outerjoin(
        Video, TranscriptSegment.video_id == Video.id
    )
    if video_identifier:
        query = query.filter(
            or_(
                Video.video_id == video_identifier,
                TranscriptSegment.video_id == video_identifier,
                TranscriptSegment.document_id == video_identifier,
            )
        )

    ordered = query.order_by(
        TranscriptSegment.t_start.asc(), TranscriptSegment.created_at.asc()
    ).all()
    results: list[TranscriptSegment] = []
    for segment in ordered:
        if osis and not _matches_osis(segment, osis):
            continue
        results.append(segment)
        if len(results) >= limit:
            break
    return results
