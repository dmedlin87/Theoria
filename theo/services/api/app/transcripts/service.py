"""Query helpers for transcript segments."""

from __future__ import annotations

import pythonbible as pb
from sqlalchemy import Integer, cast, exists, func, or_, select
from sqlalchemy.orm import Session

from ..db.models import TranscriptSegment, Video
from ..ingest.osis import expand_osis_reference, format_osis


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

    if limit <= 0:
        return []

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

    bind = session.get_bind()
    dialect_name = getattr(getattr(bind, "dialect", None), "name", None)

    if osis:
        try:
            query_ids = sorted(expand_osis_reference(osis))
        except Exception:  # pragma: no cover - defensive against malformed input
            query_ids = []
        if not query_ids:
            return []

        if dialect_name == "postgresql":
            query = query.filter(TranscriptSegment.osis_verse_ids.op("&&")(query_ids))
        else:
            json_each = func.json_each(TranscriptSegment.osis_verse_ids).table_valued(
                "value"
            )
            overlap_clause = exists(
                select(1)
                .select_from(json_each)
                .where(cast(json_each.c.value, Integer).in_(query_ids))
            )
            query = query.filter(overlap_clause)

    ordered = query.order_by(
        TranscriptSegment.t_start.asc(), TranscriptSegment.created_at.asc()
    )
    limited = ordered.limit(limit)
    return limited.all()


def canonical_primary_osis(segment: TranscriptSegment) -> str | None:
    """Return a canonical single-verse OSIS string for *segment* if possible."""

    target_id: int | None = None

    if segment.primary_osis:
        primary_ids = sorted(expand_osis_reference(segment.primary_osis))
        if primary_ids:
            target_id = primary_ids[0]

    if target_id is None and segment.osis_verse_ids:
        for verse_id in segment.osis_verse_ids:
            try:
                target_id = int(verse_id)
            except (TypeError, ValueError):
                continue
            else:
                break

    if target_id is None and segment.osis_refs:
        for reference in segment.osis_refs:
            if not reference:
                continue
            reference_ids = sorted(expand_osis_reference(reference))
            if reference_ids:
                target_id = reference_ids[0]
                break

    if target_id is None:
        return segment.primary_osis

    try:
        normalized = pb.convert_verse_ids_to_references([target_id])
    except Exception:  # pragma: no cover - pythonbible defensive guard
        return segment.primary_osis

    if not normalized:
        return segment.primary_osis

    return format_osis(normalized[0])


def _matches_osis(segment: TranscriptSegment, query: str | None) -> bool:
    """Return ``True`` when *segment* overlaps with an OSIS *query*."""

    if not query:
        return False

    query_ids = expand_osis_reference(query)
    if not query_ids:
        return False

    references: list[str] = []
    if segment.primary_osis:
        references.append(segment.primary_osis)
    if segment.osis_refs:
        references.extend(ref for ref in segment.osis_refs if ref)

    for reference in references:
        try:
            reference_ids = expand_osis_reference(reference)
        except Exception:  # pragma: no cover - defensive against malformed refs
            reference_ids = frozenset()
        if reference_ids and not reference_ids.isdisjoint(query_ids):
            return True

    return False
