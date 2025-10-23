from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import Base, CommentaryExcerptSeed
from theo.services.api.app.ingest.osis import ResolvedCommentaryAnchor
import theo.services.api.app.ingest.persistence as persistence
from theo.services.api.app.ingest.persistence import (
    IngestContext,
    _dedupe_preserve_order,
    _project_document_if_possible,
    persist_commentary_entries,
    refresh_creator_verse_rollups,
)


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


def test_dedupe_preserve_order_strips_and_omits_empty_values() -> None:
    values = ["  Alpha  ", None, "", "Beta", "Alpha", "beta", "  "]

    assert _dedupe_preserve_order(values) == ["Alpha", "Beta", "beta"]


def test_project_document_if_possible_projects_and_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[object] = []

    class _Recorder:
        def project_document(self, projection):
            captured.append(projection)

    context = IngestContext(
        settings=SimpleNamespace(),
        embedding_service=SimpleNamespace(),
        instrumentation=SimpleNamespace(),
        graph_projector=_Recorder(),
    )

    document = SimpleNamespace(
        id="doc-1",
        title="Example",
        source_type="sermon",
        topic_domains=["  Doctrine  ", "Doctrine"],
        theological_tradition="Reformed",
    )

    _project_document_if_possible(
        context,
        document,
        verses=[" John.1.1 ", "John.1.1", None],
        concepts=[" grace ", "grace"],
    )

    assert len(captured) == 1
    projection = captured[0]
    assert projection.document_id == "doc-1"
    assert projection.verses == ("John.1.1",)
    assert projection.concepts == ("grace",)
    assert projection.topic_domains == ("Doctrine",)


def test_project_document_if_possible_no_projector_is_noop() -> None:
    context = IngestContext(
        settings=SimpleNamespace(),
        embedding_service=SimpleNamespace(),
        instrumentation=SimpleNamespace(),
        graph_projector=None,
    )

    _project_document_if_possible(
        context,
        SimpleNamespace(
            id="doc-1",
            title="Example",
            source_type="sermon",
            topic_domains=None,
            theological_tradition=None,
        ),
        verses=["John.1.1"],
        concepts=["grace"],
    )


def test_refresh_creator_verse_rollups_sync_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list[str]] = []

    class _Service:
        def __init__(self, session):
            self.session = session

        def refresh_many(self, refs):
            captured.append(list(refs))

    monkeypatch.setattr(persistence, "CreatorVersePerspectiveService", _Service)

    context = IngestContext(
        settings=SimpleNamespace(creator_verse_rollups_async_refresh=False),
        embedding_service=SimpleNamespace(),
        instrumentation=SimpleNamespace(),
        graph_projector=None,
    )

    segments = [SimpleNamespace(osis_refs=["Gen.1.1", "Gen.1.1"])]

    refresh_creator_verse_rollups("session", segments, context=context)

    assert captured == [["Gen.1.1"]]


def test_refresh_creator_verse_rollups_skips_when_no_refs(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    class _Service:
        def __init__(self, *_args, **_kwargs):
            nonlocal called
            called = True

        def refresh_many(self, _refs):  # pragma: no cover - should not run
            raise AssertionError("refresh_many should not be invoked")

    monkeypatch.setattr(persistence, "CreatorVersePerspectiveService", _Service)

    context = IngestContext(
        settings=SimpleNamespace(creator_verse_rollups_async_refresh=False),
        embedding_service=SimpleNamespace(),
        instrumentation=SimpleNamespace(),
        graph_projector=None,
    )

    refresh_creator_verse_rollups("session", [SimpleNamespace(osis_refs=None)], context=context)

    assert called is False
