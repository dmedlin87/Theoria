"""Regression tests for transcript segment search helpers."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from theo.adapters.persistence.models import Document, TranscriptSegment, Video
from theo.adapters.persistence.transcript_repository import SQLAlchemyTranscriptRepository
from theo.application.dtos import TranscriptSegmentDTO, TranscriptVideoDTO
from theo.services.api.app.ingest.osis import expand_osis_reference
from theo.services.api.app.transcripts.service import (
    build_source_ref,
    canonical_primary_osis,
    search_transcript_segments,
)


def _create_transcript_segment(
    session: Session,
    *,
    document: Document,
    video: Video,
    t_start: float,
    text: str,
    osis_refs: Sequence[str] | None = None,
) -> TranscriptSegment:
    verse_ids: list[int] = []
    references = list(osis_refs or [])
    for reference in references:
        verse_ids.extend(expand_osis_reference(reference))
    unique_ids = sorted(set(verse_ids))
    segment = TranscriptSegment(
        document_id=document.id,
        video_id=video.id,
        t_start=t_start,
        t_end=t_start + 5,
        text=text,
        primary_osis=references[0] if references else None,
        osis_refs=list(references) or None,
        osis_verse_ids=unique_ids or None,
    )
    session.add(segment)
    return segment


@pytest.fixture()
def sqlite_session(api_engine) -> Session:
    """Provide a transactional session bound to the API test engine."""

    SessionLocal = sessionmaker(bind=api_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_minimal_video(session: Session, video_id: str) -> tuple[Document, Video]:
    document = Document(title=f"Doc-{video_id}")
    session.add(document)
    session.flush()
    video = Video(document_id=document.id, video_id=video_id)
    session.add(video)
    session.flush()
    return document, video


def _make_segment(
    *,
    id: str = "segment",
    document_id: str | None = "doc",
    text: str | None = "segment",
    primary_osis: str | None = None,
    osis_refs: Sequence[str] | None = None,
    osis_verse_ids: Sequence[int] | None = None,
    t_start: float | None = 0.0,
    t_end: float | None = 5.0,
    video: TranscriptVideoDTO | None = None,
) -> TranscriptSegmentDTO:
    """Return a transcript segment DTO for pure function tests."""

    return TranscriptSegmentDTO(
        id=id,
        document_id=document_id,
        text=text,
        primary_osis=primary_osis,
        osis_refs=tuple(osis_refs or ()),
        osis_verse_ids=tuple(osis_verse_ids or ()),
        t_start=t_start,
        t_end=t_end,
        video=video,
    )


def test_search_transcript_segments_filters_in_sql(sqlite_session: Session) -> None:
    """The search helper should only return segments overlapping the OSIS query."""

    document, video = _seed_minimal_video(sqlite_session, "vid-sql")
    other_document, other_video = _seed_minimal_video(sqlite_session, "vid-other")

    match = _create_transcript_segment(
        sqlite_session,
        document=document,
        video=video,
        t_start=1,
        text="matching",
        osis_refs=["John.3.16"],
    )
    overlap = _create_transcript_segment(
        sqlite_session,
        document=document,
        video=video,
        t_start=2,
        text="overlap",
        osis_refs=["John.3.16-17"],
    )
    _create_transcript_segment(
        sqlite_session,
        document=document,
        video=video,
        t_start=3,
        text="different",
        osis_refs=["Genesis.1.1"],
    )
    _create_transcript_segment(
        sqlite_session,
        document=other_document,
        video=other_video,
        t_start=4,
        text="other video",
        osis_refs=["John.3.16"],
    )
    sqlite_session.commit()

    repository = SQLAlchemyTranscriptRepository(sqlite_session)
    results = search_transcript_segments(
        repository,
        osis="John.3.16",
        video_identifier="vid-sql",
        limit=5,
    )

    assert [segment.text for segment in results] == ["matching", "overlap"]
    assert [segment.primary_osis for segment in results] == [
        "John.3.16",
        "John.3.16-17",
    ]


def test_search_transcript_segments_emits_overlap_clause(sqlite_session: Session) -> None:
    """The generated SQL should include an overlap predicate for OSIS ids."""

    document, video = _seed_minimal_video(sqlite_session, "vid-overlap")

    _create_transcript_segment(
        sqlite_session,
        document=document,
        video=video,
        t_start=1,
        text="one",
        osis_refs=["John.3.16"],
    )
    sqlite_session.commit()

    executed: list[str] = []

    def _capture_sql(*_args, statement: str, **_kwargs) -> None:
        executed.append(statement)

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ) -> None:  # pragma: no cover - simple instrumentation hook
        _capture_sql(statement=statement)

    event.listen(
        sqlite_session.bind,
        "before_cursor_execute",
        _before_cursor_execute,
    )
    try:
        repository = SQLAlchemyTranscriptRepository(sqlite_session)
        search_transcript_segments(
            repository,
            osis="John.3.16",
            video_identifier="vid-overlap",
            limit=5,
        )
    finally:
        event.remove(
            sqlite_session.bind,
            "before_cursor_execute",
            _before_cursor_execute,
        )

    overlap_statements = [
        stmt
        for stmt in executed
        if stmt.lstrip().upper().startswith("SELECT")
    ]
    assert any("json_each" in stmt or "&&" in stmt for stmt in overlap_statements)


def test_build_source_ref_formats_known_platform_prefix() -> None:
    """YouTube links should use the dedicated prefix with a mm:ss timestamp."""

    video = TranscriptVideoDTO(
        id=None,
        video_id="yt-123",
        title=None,
        url="https://www.youtube.com/watch?v=yt-123",
    )

    reference = build_source_ref(video, 125.9)

    assert reference == "youtube:yt-123#t=02:05"


def test_build_source_ref_returns_none_without_minimum_metadata() -> None:
    """Missing identifiers or timestamps should short-circuit to ``None``."""

    assert build_source_ref(None, 15.0) is None
    assert (
        build_source_ref(
            TranscriptVideoDTO(id=None, video_id=None, title=None, url=None), 15.0
        )
        is None
    )
    assert (
        build_source_ref(
            TranscriptVideoDTO(id=None, video_id="clip", title=None, url=None), None
        )
        is None
    )

    video = TranscriptVideoDTO(
        id=None,
        video_id="clip",
        title=None,
        url="https://cdn.example.com/clip.mp4",
    )

    assert build_source_ref(video, 59.0) == "video:clip#t=00:59"


def test_canonical_primary_osis_normalizes_primary_range() -> None:
    """Ranges collapse to their first verse to keep identifiers stable."""

    segment = _make_segment(primary_osis="John.3.16-John.3.17")

    assert canonical_primary_osis(segment) == "John.3.16"


def test_canonical_primary_osis_falls_back_to_verse_ids() -> None:
    """Verse identifiers stored on the segment should seed canonical output."""

    verse_ids = sorted(expand_osis_reference("John.3.16"))
    segment = _make_segment(primary_osis=None, osis_verse_ids=list(verse_ids))

    assert canonical_primary_osis(segment) == "John.3.16"


def test_canonical_primary_osis_uses_additional_references_when_needed() -> None:
    """Explicit OSIS references act as the final fallback for canonicalization."""

    segment = _make_segment(
        primary_osis=None,
        osis_verse_ids=None,
        osis_refs=["John.3.16", "John.3.17"],
    )

    assert canonical_primary_osis(segment) == "John.3.16"
