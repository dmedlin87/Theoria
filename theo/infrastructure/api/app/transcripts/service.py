"""Query helpers for transcript segments."""

from __future__ import annotations

import pythonbible as pb

from theo.application.dtos import TranscriptSegmentDTO, TranscriptVideoDTO
from theo.application.repositories.transcript_repository import TranscriptRepository
from theo.domain.research.osis import expand_osis_reference, format_osis


def build_source_ref(video: TranscriptVideoDTO | None, t_start: float | None) -> str | None:
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
    repository: TranscriptRepository,
    *,
    osis: str | None,
    video_identifier: str | None,
    limit: int,
) -> list[TranscriptSegmentDTO]:
    """Return transcript segments filtered by OSIS and/or video identifier."""

    return repository.search_segments(
        osis=osis, video_identifier=video_identifier, limit=limit
    )


def canonical_primary_osis(segment: TranscriptSegmentDTO) -> str | None:
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


def _matches_osis(segment: TranscriptSegmentDTO, query: str | None) -> bool:
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
