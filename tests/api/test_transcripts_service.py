"""Regression tests for transcript segment search helpers."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from theo.services.api.app.db.models import Document, TranscriptSegment, Video
from theo.services.api.app.ingest.osis import expand_osis_reference
from theo.services.api.app.transcripts.service import search_transcript_segments


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

    results = search_transcript_segments(
        sqlite_session,
        osis="John.3.16",
        video_identifier="vid-sql",
        limit=5,
    )

    assert results == [match, overlap]


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
        search_transcript_segments(
            sqlite_session,
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
