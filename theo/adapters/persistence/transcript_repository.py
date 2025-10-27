"""SQLAlchemy-backed transcript repository implementation."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Integer, cast, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from theo.application.dtos import TranscriptSegmentDTO, TranscriptVideoDTO
from theo.application.observability import trace_repository_call
from theo.application.repositories.transcript_repository import TranscriptRepository
from theo.domain.research.osis import expand_osis_reference

from .base_repository import BaseRepository
from .models import TranscriptSegment, Video


class SQLAlchemyTranscriptRepository(
    BaseRepository[TranscriptSegment], TranscriptRepository
):
    """Retrieve transcript segments using a SQLAlchemy session."""

    def __init__(self, session: Session):
        super().__init__(session)

    def search_segments(
        self,
        *,
        osis: str | None,
        video_identifier: str | None,
        limit: int,
    ) -> list[TranscriptSegmentDTO]:
        with trace_repository_call(
            "transcript",
            "search_segments",
            attributes={
                "osis": osis,
                "video_identifier": video_identifier,
                "limit": limit,
            },
        ) as trace:
            if limit <= 0:
                trace.record_result_count(0)
                return []

            query = (
                self.session.query(TranscriptSegment)
                .options(joinedload(TranscriptSegment.video))
                .outerjoin(Video, TranscriptSegment.video_id == Video.id)
            )

            if video_identifier:
                query = query.filter(
                    or_(
                        Video.video_id == video_identifier,
                        TranscriptSegment.video_id == video_identifier,
                        TranscriptSegment.document_id == video_identifier,
                    )
                )

            bind = self.session.get_bind()
            dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
            trace.set_attribute("dialect", dialect_name or "unknown")

            if osis:
                try:
                    query_ids = sorted(expand_osis_reference(osis))
                except Exception:  # pragma: no cover - guard against malformed inputs
                    query_ids = []
                if not query_ids:
                    trace.record_result_count(0)
                    return []

                trace.set_attribute("verse_id_count", len(query_ids))

                if dialect_name == "postgresql":
                    query = query.filter(TranscriptSegment.osis_verse_ids.op("&&")(query_ids))
                else:
                    json_each = func.json_each(
                        TranscriptSegment.osis_verse_ids
                    ).table_valued("value")
                    overlap_clause = exists(
                        select(1)
                        .select_from(json_each)
                        .where(cast(json_each.c.value, Integer).in_(query_ids))
                    )
                    query = query.filter(overlap_clause)

            ordered = query.order_by(
                TranscriptSegment.t_start.asc(), TranscriptSegment.created_at.asc()
            )
            segments = ordered.limit(limit).all()
            trace.record_result_count(len(segments))

            return [self._to_dto(segment) for segment in segments]

    @staticmethod
    def _normalize_strings(raw_refs: Iterable[str | None] | None) -> tuple[str, ...]:
        if not raw_refs:
            return ()
        values: list[str] = []
        for item in raw_refs:
            if isinstance(item, str) and item.strip():
                values.append(item.strip())
        return tuple(values)

    @staticmethod
    def _normalize_ints(raw_ids: Iterable[int | str | None] | None) -> tuple[int, ...]:
        if not raw_ids:
            return ()
        results: list[int] = []
        for item in raw_ids:
            if isinstance(item, int):
                results.append(item)
            else:
                try:
                    value = int(item)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
                results.append(value)
        return tuple(sorted(set(results)))

    def _to_dto(self, segment: TranscriptSegment) -> TranscriptSegmentDTO:
        video = None
        if segment.video is not None:
            video = TranscriptVideoDTO(
                id=str(segment.video.id) if segment.video.id is not None else None,
                video_id=segment.video.video_id,
                title=segment.video.title,
                url=segment.video.url,
            )

        return TranscriptSegmentDTO(
            id=str(segment.id),
            document_id=segment.document_id,
            text=segment.text,
            primary_osis=segment.primary_osis,
            osis_refs=self._normalize_strings(segment.osis_refs),
            osis_verse_ids=self._normalize_ints(segment.osis_verse_ids),
            t_start=segment.t_start,
            t_end=segment.t_end,
            video=video,
        )


__all__ = ["SQLAlchemyTranscriptRepository"]
