"""Regression tests for verse-range-aware seed lookups."""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import (
    Base,
    CommentaryExcerptSeed,
    ContradictionSeed,
    HarmonySeed,
)
from theo.infrastructure.api.app.db.verse_graph import load_seed_relationships
from theo.infrastructure.api.app.ingest.osis import expand_osis_reference
from theo.infrastructure.api.app.research.commentaries import search_commentaries
from theo.infrastructure.api.app.research.contradictions import search_contradictions


def _range(osis: str) -> tuple[int | None, int | None]:
    ids = expand_osis_reference(osis)
    if not ids:
        return None, None
    return min(ids), max(ids)


def _setup_engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def _count_selects(engine):
    stats = {"count": 0}

    def _before_execute(_, __, statement, ___, ____, _____):
        if statement.lstrip().upper().startswith("SELECT"):
            stats["count"] += 1

    event.listen(engine, "before_cursor_execute", _before_execute)
    try:
        yield stats
    finally:
        event.remove(engine, "before_cursor_execute", _before_execute)


def test_search_contradictions_uses_range_filters() -> None:
    engine = _setup_engine()
    with Session(engine) as session:
        start_a, end_a = _range("John.3.16")
        start_b, end_b = _range("Matthew.5.44")
        session.add(
            ContradictionSeed(
                id="c1",
                osis_a="John.3.16",
                osis_b="Matthew.5.44",
                summary="Tension",
                source="Digest",
                tags=["love"],
                weight=2.0,
                perspective="skeptical",
                start_verse_id=start_a,
                end_verse_id=end_a,
                start_verse_id_b=start_b,
                end_verse_id_b=end_b,
            )
        )
        h_start_a, h_end_a = _range("John.3.16")
        h_start_b, h_end_b = _range("Luke.6.27")
        session.add(
            HarmonySeed(
                id="h1",
                osis_a="John.3.16",
                osis_b="Luke.6.27",
                summary="Harmony",
                source="Notes",
                tags=["love"],
                weight=1.0,
                perspective="apologetic",
                start_verse_id=h_start_a,
                end_verse_id=h_end_a,
                start_verse_id_b=h_start_b,
                end_verse_id_b=h_end_b,
            )
        )
        # Seed unrelated entries that should be ignored.
        g_start_a, g_end_a = _range("Gen.1.1")
        g_start_b, g_end_b = _range("Gen.1.2")
        session.add(
            ContradictionSeed(
                id="c2",
                osis_a="Gen.1.1",
                osis_b="Gen.1.2",
                summary="Creation",
                source="Digest",
                tags=["creation"],
                weight=3.0,
                perspective="skeptical",
                start_verse_id=g_start_a,
                end_verse_id=g_end_a,
                start_verse_id_b=g_start_b,
                end_verse_id_b=g_end_b,
            )
        )
        # Stale row with incorrect OSIS but overlapping numeric range should be ignored.
        session.add(
            ContradictionSeed(
                id="c3",
                osis_a="Gen.1.1",
                osis_b="Gen.1.2",
                summary="Stale",
                source="Digest",
                tags=["creation"],
                weight=1.0,
                perspective="skeptical",
                start_verse_id=start_a,
                end_verse_id=end_a,
                start_verse_id_b=start_b,
                end_verse_id_b=end_b,
            )
        )
        session.commit()

        with _count_selects(engine) as stats:
            results = search_contradictions(session, osis="John.3.16", limit=5)
        assert stats["count"] == 2
        assert [item.id for item in results] == ["c1", "h1"]

        with _count_selects(engine) as stats:
            filtered = search_contradictions(
                session,
                osis=["John.3.16", "John.3.17"],
                perspectives=["apologetic"],
                limit=5,
            )
        assert stats["count"] == 2
        assert [item.id for item in filtered] == ["h1"]


def test_search_contradictions_supports_multiple_references() -> None:
    engine = _setup_engine()
    with Session(engine) as session:
        start_a, end_a = _range("John.3.16")
        start_b, end_b = _range("Matthew.5.44")
        session.add(
            ContradictionSeed(
                id="c-multi",
                osis_a="John.3.16",
                osis_b="Matthew.5.44",
                summary="Overlap",
                source="Digest",
                tags=["love"],
                weight=2.0,
                perspective="skeptical",
                start_verse_id=start_a,
                end_verse_id=end_a,
                start_verse_id_b=start_b,
                end_verse_id_b=end_b,
            )
        )
        h_start_a, h_end_a = _range("John.3.17")
        h_start_b, h_end_b = _range("Luke.6.27")
        session.add(
            HarmonySeed(
                id="h-multi",
                osis_a="John.3.17",
                osis_b="Luke.6.27",
                summary="Harmony",
                source="Notes",
                tags=["love"],
                weight=1.5,
                perspective="apologetic",
                start_verse_id=h_start_a,
                end_verse_id=h_end_a,
                start_verse_id_b=h_start_b,
                end_verse_id_b=h_end_b,
            )
        )
        off_start_a, off_end_a = _range("Gen.1.1")
        off_start_b, off_end_b = _range("Gen.1.2")
        session.add(
            ContradictionSeed(
                id="c-off",
                osis_a="Gen.1.1",
                osis_b="Gen.1.2",
                summary="Creation",
                source="Digest",
                tags=["creation"],
                weight=3.0,
                perspective="skeptical",
                start_verse_id=off_start_a,
                end_verse_id=off_end_a,
                start_verse_id_b=off_start_b,
                end_verse_id_b=off_end_b,
            )
        )
        session.commit()

    with Session(engine) as session:
        with _count_selects(engine) as stats:
            results = search_contradictions(
                session,
                osis=["John.3.16", "John.3.17"],
                limit=10,
            )
        assert stats["count"] == 2
        assert {item.id for item in results} == {"c-multi", "h-multi"}


def test_search_commentaries_uses_range_filters() -> None:
    engine = _setup_engine()
    with Session(engine) as session:
        start_value, end_value = _range("John.3.16")
        session.add(
            CommentaryExcerptSeed(
                id="m1",
                osis="John.3.16",
                title="Commentary",
                excerpt="Insight",
                source="Fathers",
                perspective="neutral",
                tags=["love"],
                start_verse_id=start_value,
                end_verse_id=end_value,
            )
        )
        g_start, g_end = _range("Gen.1.1")
        session.add(
            CommentaryExcerptSeed(
                id="m2",
                osis="Gen.1.1",
                title="Genesis",
                excerpt="Creation",
                source="Digest",
                perspective="neutral",
                tags=["creation"],
                start_verse_id=g_start,
                end_verse_id=g_end,
            )
        )
        # Row with mismatched numeric range should be filtered at Python level.
        session.add(
            CommentaryExcerptSeed(
                id="m3",
                osis="Gen.1.1",
                title="Mismatch",
                excerpt="Mismatch",
                source="Digest",
                perspective="neutral",
                tags=["creation"],
                start_verse_id=start_value,
                end_verse_id=end_value,
            )
        )
        session.commit()

        with _count_selects(engine) as stats:
            results = search_commentaries(session, osis="John.3.16", limit=5)
        assert stats["count"] == 1
        assert [item.id for item in results] == ["m1"]

        with _count_selects(engine) as stats:
            none = search_commentaries(
                session,
                osis="John.3.16",
                perspectives=["skeptical"],
                limit=5,
            )
        assert stats["count"] == 1
        assert none == []


def test_search_commentaries_handles_multiple_references() -> None:
    engine = _setup_engine()
    with Session(engine) as session:
        start_john16, end_john16 = _range("John.3.16")
        session.add(
            CommentaryExcerptSeed(
                id="m-john16",
                osis="John.3.16",
                title="John 3:16",
                excerpt="Love the world",
                source="Digest",
                perspective="neutral",
                tags=["love"],
                start_verse_id=start_john16,
                end_verse_id=end_john16,
            )
        )

        start_john17, end_john17 = _range("John.3.17")
        session.add(
            CommentaryExcerptSeed(
                id="m-john17",
                osis="John.3.17",
                title="John 3:17",
                excerpt="Not to condemn",
                source="Digest",
                perspective="neutral",
                tags=["love"],
                start_verse_id=start_john17,
                end_verse_id=end_john17,
            )
        )

        off_start, off_end = _range("Gen.1.1")
        session.add(
            CommentaryExcerptSeed(
                id="m-genesis",
                osis="Gen.1.1",
                title="Genesis",
                excerpt="Creation",
                source="Digest",
                perspective="neutral",
                tags=["creation"],
                start_verse_id=off_start,
                end_verse_id=off_end,
            )
        )
        session.commit()

        with _count_selects(engine) as stats:
            results = search_commentaries(
                session,
                osis=["John.3.16", "John.3.17"],
                limit=10,
            )

        assert stats["count"] == 1
        assert {item.id for item in results} == {"m-john16", "m-john17"}


def test_load_seed_relationships_bounds_queries() -> None:
    engine = _setup_engine()
    with Session(engine) as session:
        start_a, end_a = _range("John.3.16")
        start_b, end_b = _range("Luke.6.27")
        session.add(
            HarmonySeed(
                id="h-loaded",
                osis_a="John.3.16",
                osis_b="Luke.6.27",
                summary="Harmony",
                source="Notes",
                tags=["love"],
                weight=1.0,
                perspective="apologetic",
                start_verse_id=start_a,
                end_verse_id=end_a,
                start_verse_id_b=start_b,
                end_verse_id_b=end_b,
            )
        )
        session.add(
            ContradictionSeed(
                id="c-loaded",
                osis_a="John.3.16",
                osis_b="Matthew.5.44",
                summary="Tension",
                source="Digest",
                tags=["love"],
                weight=2.0,
                perspective="skeptical",
                start_verse_id=start_a,
                end_verse_id=end_a,
                start_verse_id_b=start_b,
                end_verse_id_b=end_b,
            )
        )
        session.add(
            CommentaryExcerptSeed(
                id="m-loaded",
                osis="John.3.16",
                title="Commentary",
                excerpt="Insight",
                source="Digest",
                perspective="neutral",
                tags=["love"],
                start_verse_id=start_a,
                end_verse_id=end_a,
            )
        )
        session.commit()

    with Session(engine) as session:
        with _count_selects(engine) as stats:
            relationships = load_seed_relationships(session, "John.3.16")
        assert stats["count"] == 3
        assert {item.id for item in relationships.contradictions} == {"c-loaded"}
        assert {item.id for item in relationships.harmonies} == {"h-loaded"}
        assert {item.id for item in relationships.commentaries} == {"m-loaded"}
