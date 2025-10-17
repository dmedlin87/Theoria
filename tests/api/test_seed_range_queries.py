from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import (
    Base,
    CommentaryExcerptSeed,
    ContradictionSeed,
    HarmonySeed,
)
from theo.services.api.app.db.verse_graph import load_seed_relationships
from theo.services.api.app.ingest.osis import expand_osis_reference
from theo.services.api.app.research.commentaries import search_commentaries
from theo.services.api.app.research.contradictions import search_contradictions


def _bounds(reference: str) -> tuple[int, int]:
    verse_ids = expand_osis_reference(reference)
    assert verse_ids, f"reference {reference} should resolve to verse ids"
    return min(verse_ids), max(verse_ids)


@contextmanager
def _count_queries(engine):
    statements: list[str] = []

    def _before_execute(  # type: ignore[no-untyped-def]
        conn, cursor, statement, parameters, context, executemany
    ) -> None:
        statements.append(str(statement))

    event.listen(engine, "before_cursor_execute", _before_execute)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _before_execute)


@pytest.fixture()
def seeded_engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        start_a, end_a = _bounds("Gen.1.1")
        start_b, end_b = _bounds("Gen.1.2")
        session.add(
            ContradictionSeed(
                id="contradiction-match",
                osis_a="Gen.1.1",
                osis_b="Gen.1.2",
                summary="matching contradiction",
                source="test",
                tags=["creation"],
                weight=1.0,
                perspective="skeptical",
                start_verse_id_a=start_a,
                end_verse_id_a=end_a,
                start_verse_id_b=start_b,
                end_verse_id_b=end_b,
            )
        )
        start_a, end_a = _bounds("Exod.1.1")
        start_b, end_b = _bounds("Exod.1.2")
        session.add(
            ContradictionSeed(
                id="contradiction-miss",
                osis_a="Exod.1.1",
                osis_b="Exod.1.2",
                summary="non matching contradiction",
                source="test",
                tags=["exodus"],
                weight=1.0,
                perspective="skeptical",
                start_verse_id_a=start_a,
                end_verse_id_a=end_a,
                start_verse_id_b=start_b,
                end_verse_id_b=end_b,
            )
        )
        start_a, end_a = _bounds("Gen.1.1")
        start_b, end_b = _bounds("Gen.1.3")
        session.add(
            HarmonySeed(
                id="harmony-match",
                osis_a="Gen.1.1",
                osis_b="Gen.1.3",
                summary="matching harmony",
                source="test",
                tags=["creation"],
                weight=1.0,
                perspective="apologetic",
                start_verse_id_a=start_a,
                end_verse_id_a=end_a,
                start_verse_id_b=start_b,
                end_verse_id_b=end_b,
            )
        )
        start_a, end_a = _bounds("Ps.1.1")
        start_b, end_b = _bounds("Ps.1.2")
        session.add(
            HarmonySeed(
                id="harmony-miss",
                osis_a="Ps.1.1",
                osis_b="Ps.1.2",
                summary="non matching harmony",
                source="test",
                tags=["psalms"],
                weight=1.0,
                perspective="apologetic",
                start_verse_id_a=start_a,
                end_verse_id_a=end_a,
                start_verse_id_b=start_b,
                end_verse_id_b=end_b,
            )
        )
        start_ref, end_ref = _bounds("Gen.1.1-Gen.1.2")
        session.add(
            CommentaryExcerptSeed(
                id="commentary-match",
                osis="Gen.1.1-Gen.1.2",
                title="Genesis commentary",
                excerpt="Matching excerpt",
                source="test",
                perspective="neutral",
                tags=["creation"],
                start_verse_id=start_ref,
                end_verse_id=end_ref,
            )
        )
        start_ref, end_ref = _bounds("Exod.1.1")
        session.add(
            CommentaryExcerptSeed(
                id="commentary-miss",
                osis="Exod.1.1",
                title="Exodus commentary",
                excerpt="Not requested",
                source="test",
                perspective="neutral",
                tags=["exodus"],
                start_verse_id=start_ref,
                end_verse_id=end_ref,
            )
        )
        session.commit()

    try:
        yield engine
    finally:
        engine.dispose()


def test_load_seed_relationships_uses_range_filters(seeded_engine):
    engine = seeded_engine
    with Session(engine) as session:
        with _count_queries(engine) as statements:
            relationships = load_seed_relationships(session, "Gen.1.1")

    assert len(statements) == 3
    assert any("start_verse_id_a" in stmt for stmt in statements)
    assert {seed.id for seed in relationships.contradictions} == {"contradiction-match"}
    assert {seed.id for seed in relationships.harmonies} == {"harmony-match"}
    assert {seed.id for seed in relationships.commentaries} == {"commentary-match"}


def test_search_contradictions_skips_harmony_query_when_filtered(seeded_engine):
    engine = seeded_engine
    with Session(engine) as session:
        with _count_queries(engine) as statements:
            items = search_contradictions(
                session,
                osis="Gen.1.1",
                perspectives=["skeptical"],
                limit=10,
            )

    assert len(statements) == 1
    assert {item.id for item in items} == {"contradiction-match"}


def test_search_commentaries_filters_by_range(seeded_engine):
    engine = seeded_engine
    with Session(engine) as session:
        with _count_queries(engine) as statements:
            items = search_commentaries(
                session,
                osis="Gen.1.1",
                perspectives=None,
                limit=10,
            )

    assert len(statements) == 1
    assert any("start_verse_id" in stmt for stmt in statements)
    assert [item.id for item in items] == ["commentary-match"]
