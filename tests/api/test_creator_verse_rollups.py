from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from theo.application.facades.database import Base
from theo.services.api.app.db.models import (
    Creator,
    CreatorClaim,
    CreatorVerseRollup,
    Document,
    TranscriptQuote,
    TranscriptQuoteVerse,
    TranscriptSegment,
    TranscriptSegmentVerse,
    Video,
)
from theo.services.api.app.ingest.osis import expand_osis_reference
from theo.services.api.app.ingest.persistence import refresh_creator_verse_rollups
from theo.services.api.app.ingest.stages import IngestContext, Instrumentation


class _DummyEmbeddingService:
    def embed(self, texts):  # type: ignore[no-untyped-def]
        return [[] for _ in texts]


@pytest.fixture()
def sqlite_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path}/creator_rollups.sqlite")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _index_refs(session: Session, refs: list[str], factory):  # type: ignore[no-untyped-def]
    verse_ids: set[int] = set()
    for ref in refs:
        verse_ids.update(int(verse_id) for verse_id in expand_osis_reference(ref))
    for verse_id in sorted(verse_ids):
        session.add(factory(verse_id))


def test_refresh_creator_rollups_filters_matching_claims(sqlite_session: Session) -> None:
    context = IngestContext(
        settings=SimpleNamespace(creator_verse_rollups_async_refresh=False),
        embedding_service=_DummyEmbeddingService(),
        instrumentation=Instrumentation(span=None),
    )

    creator = Creator(name="Test Creator")
    document = Document(title="Doc", source_type="transcript")
    sqlite_session.add_all([creator, document])
    sqlite_session.flush()

    video = Video(
        creator_id=creator.id,
        document_id=document.id,
        video_id="vid-1",
        title="Video",
    )
    sqlite_session.add(video)
    sqlite_session.flush()

    segment_john = TranscriptSegment(
        document_id=document.id,
        video_id=video.id,
        t_start=0.0,
        t_end=5.0,
        text="Teaching on John 3:5 and 3:6",
        primary_osis="John.3.5",
        osis_refs=["John.3.5", "John.3.6"],
    )
    segment_other = TranscriptSegment(
        document_id=document.id,
        video_id=video.id,
        t_start=10.0,
        t_end=20.0,
        text="Thoughts on Genesis 1:1",
        primary_osis="Gen.1.1",
        osis_refs=["Gen.1.1"],
    )
    sqlite_session.add_all([segment_john, segment_other])

    sqlite_session.flush()

    _index_refs(
        sqlite_session,
        segment_john.osis_refs or [],
        lambda verse_id: TranscriptSegmentVerse(segment=segment_john, verse_id=verse_id),
    )
    _index_refs(
        sqlite_session,
        segment_other.osis_refs or [],
        lambda verse_id: TranscriptSegmentVerse(segment=segment_other, verse_id=verse_id),
    )

    quote_john = TranscriptQuote(
        video_id=video.id,
        segment=segment_john,
        quote_md="Unless one is born of water and the Spirit...",
        osis_refs=["John.3.5"],
        source_ref="vid-1#0",
        salience=1.0,
    )
    quote_extra = TranscriptQuote(
        video_id=video.id,
        segment=segment_john,
        quote_md="Jesus continues in verse 6",
        osis_refs=["John.3.6"],
        source_ref="vid-1#1",
        salience=0.2,
    )
    sqlite_session.add_all([quote_john, quote_extra])

    sqlite_session.flush()

    _index_refs(
        sqlite_session,
        quote_john.osis_refs or [],
        lambda verse_id: TranscriptQuoteVerse(quote=quote_john, verse_id=verse_id),
    )
    _index_refs(
        sqlite_session,
        quote_extra.osis_refs or [],
        lambda verse_id: TranscriptQuoteVerse(quote=quote_extra, verse_id=verse_id),
    )

    claim_john = CreatorClaim(
        creator_id=creator.id,
        video_id=video.id,
        segment=segment_john,
        topic="Baptism",
        stance="for",
        claim_md="John 3:5 emphasises new birth.",
        confidence=0.9,
    )
    claim_other = CreatorClaim(
        creator_id=creator.id,
        video_id=video.id,
        segment=segment_other,
        topic="Creation",
        stance="neutral",
        claim_md="Genesis 1:1 summary.",
        confidence=0.5,
    )
    sqlite_session.add_all([claim_john, claim_other])

    sqlite_session.flush()

    matching_quote_id = quote_john.id
    extra_quote_id = quote_extra.id

    refresh_creator_verse_rollups(sqlite_session, [segment_john], context=context)

    sqlite_session.expire_all()

    rollups = sqlite_session.query(CreatorVerseRollup).all()
    rollup_map = {rollup.osis: rollup for rollup in rollups}
    assert set(rollup_map) == {"John.3.5", "John.3.6"}

    john_rollup = rollup_map["John.3.5"]
    assert john_rollup.creator_id == creator.id
    assert john_rollup.claim_count == 1
    assert john_rollup.top_quote_ids == [matching_quote_id]
    assert john_rollup.stance_counts == {"for": 1}

    john_six_rollup = rollup_map["John.3.6"]
    assert john_six_rollup.creator_id == creator.id
    assert john_six_rollup.claim_count == 1
    assert john_six_rollup.top_quote_ids == [extra_quote_id]
