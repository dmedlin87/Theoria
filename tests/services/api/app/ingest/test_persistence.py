from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import Base, CommentaryExcerptSeed
from theo.services.api.app.ingest.osis import ResolvedCommentaryAnchor
from theo.services.api.app.ingest.persistence import persist_commentary_entries


def test_persist_commentary_entries_avoids_collisions_without_note_id() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    shared_prefix = (
        "See previous verse for context and understanding. Additional guidance "
        "about applying this teaching in practice."
    )
    entry_one = ResolvedCommentaryAnchor(
        osis="John.1.1",
        excerpt=f"{shared_prefix} Focus on daily reflection.",
        source="Test",
        perspective="neutral",
        tags=None,
        note_id=None,
    )
    entry_two = ResolvedCommentaryAnchor(
        osis="John.1.1",
        excerpt=f"{shared_prefix} Consider community discussion.",
        source="Test",
        perspective="neutral",
        tags=None,
        note_id=None,
    )

    with Session(engine) as session:
        result = persist_commentary_entries(session, entries=[entry_one, entry_two])

    assert result.inserted == 2

    with Session(engine) as session:
        stored = session.query(CommentaryExcerptSeed).order_by(CommentaryExcerptSeed.id).all()

    assert len(stored) == 2
    assert stored[0].id != stored[1].id
    assert {row.excerpt for row in stored} == {
        entry_one.excerpt,
        entry_two.excerpt,
    }
