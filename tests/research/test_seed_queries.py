"""Regression tests for verse-range-aware seed lookups."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from theo.services.api.app.db.models import Base, CommentaryExcerptSeed, ContradictionSeed, HarmonySeed
from theo.services.api.app.ingest.osis import expand_osis_reference
from theo.services.api.app.research.commentaries import search_commentaries
from theo.services.api.app.research.contradictions import search_contradictions


def _range(osis: str) -> tuple[int | None, int | None]:
    ids = expand_osis_reference(osis)
    if not ids:
        return None, None
    return min(ids), max(ids)


def _setup_engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return engine


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
        session.commit()

        results = search_contradictions(session, osis="John.3.16", limit=5)
        assert [item.id for item in results] == ["c1", "h1"]

        filtered = search_contradictions(
            session,
            osis="John.3.16",
            perspectives=["apologetic"],
            limit=5,
        )
        assert [item.id for item in filtered] == ["h1"]


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
        session.commit()

        results = search_commentaries(session, osis="John.3.16", limit=5)
        assert [item.id for item in results] == ["m1"]

        none = search_commentaries(
            session,
            osis="John.3.16",
            perspectives=["skeptical"],
            limit=5,
        )
        assert none == []
