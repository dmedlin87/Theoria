from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
import sys

import pytest
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades import database as database_module  # noqa: E402
from theo.application.facades.database import (  # noqa: E402  # import after path tweak
    Base,
    configure_engine,
    get_engine,
)
from theo.services.api.app.db.models import Document, Passage, PassageVerse  # noqa: E402
from theo.services.api.app.ingest.osis import expand_osis_reference  # noqa: E402
from theo.services.api.app.models.verses import VerseMentionsFilters  # noqa: E402
from theo.services.api.app.retriever.verses import (  # noqa: E402
    get_verse_timeline,
)


def _prepare_engine(tmp_path: Path):
    configure_engine(f"sqlite:///{tmp_path / 'timeline.db'}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return engine


def _seed_documents(session: Session) -> None:
    doc1 = Document(
        id="doc-1",
        title="First",
        source_type="pdf",
        authors=["Alice"],
        pub_date=date(2023, 1, 15),
    )
    doc2 = Document(
        id="doc-2",
        title="Second",
        source_type="pdf",
        authors=["Bob"],
        pub_date=date(2023, 1, 28),
    )
    doc3 = Document(
        id="doc-3",
        title="Third",
        source_type="markdown",
        authors=["Alice"],
        pub_date=None,
        created_at=datetime(2023, 3, 5, tzinfo=UTC),
    )
    doc4 = Document(
        id="doc-4",
        title="Fourth",
        source_type="pdf",
        authors=["Carol"],
        pub_date=date(2022, 12, 3),
    )

    session.add_all([doc1, doc2, doc3, doc4])
    session.flush()

    john_ids = list(sorted(expand_osis_reference("John.3.16")))

    passages = [
        Passage(
            id="p-1",
            document_id=doc1.id,
            text="Ref",
            osis_ref="John.3.16",
            osis_verse_ids=john_ids,
        ),
        Passage(
            id="p-2",
            document_id=doc2.id,
            text="Ref",
            osis_ref="John.3.16",
            osis_verse_ids=john_ids,
        ),
        Passage(
            id="p-3",
            document_id=doc3.id,
            text="Ref",
            osis_ref="John.3.16",
            osis_verse_ids=john_ids,
        ),
        Passage(
            id="p-4",
            document_id=doc4.id,
            text="Ref",
            osis_ref="John.3.16",
            osis_verse_ids=john_ids,
        ),
    ]
    session.add_all(passages)
    session.add_all(
        [
            PassageVerse(passage_id=passage.id, verse_id=verse_id)
            for passage in passages
            for verse_id in john_ids
        ]
    )
    session.commit()
@contextmanager
def _seeded_session(tmp_path: Path):
    engine = _prepare_engine(tmp_path)
    try:
        with Session(engine) as session:
            _seed_documents(session)
            yield session
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_get_verse_timeline_groups_mentions_by_month(tmp_path) -> None:
    with _seeded_session(tmp_path) as session:
        response = get_verse_timeline(
            session=session,
            osis="John.3.16",
            window="month",
            filters=VerseMentionsFilters(),
        )

    assert response.window == "month"
    assert response.total_mentions == 4
    assert len(response.buckets) == 3

    labels = {bucket.label: bucket for bucket in response.buckets}
    assert labels["2023-01"].count == 2
    assert sorted(labels["2023-01"].document_ids) == ["doc-1", "doc-2"]
    assert labels["2023-03"].count == 1
    assert labels["2023-03"].document_ids == ["doc-3"]
    assert labels["2022-12"].count == 1


def test_get_verse_timeline_filters_by_source_type(tmp_path) -> None:
    with _seeded_session(tmp_path) as session:
        filtered = get_verse_timeline(
            session=session,
            osis="John.3.16",
            window="month",
            filters=VerseMentionsFilters(source_type="pdf"),
        )

    assert filtered.total_mentions == 3
    labels = {bucket.label: bucket for bucket in filtered.buckets}
    assert set(labels) == {"2023-01", "2022-12"}
    assert labels["2023-01"].count == 2
    assert sorted(labels["2023-01"].document_ids) == ["doc-1", "doc-2"]
    assert labels["2022-12"].count == 1
    assert labels["2022-12"].document_ids == ["doc-4"]


def test_get_verse_timeline_respects_limit(tmp_path) -> None:
    with _seeded_session(tmp_path) as session:
        limited = get_verse_timeline(
            session=session,
            osis="John.3.16",
            window="month",
            limit=2,
            filters=VerseMentionsFilters(),
        )

    assert len(limited.buckets) == 2
    labels = {bucket.label: bucket for bucket in limited.buckets}
    assert set(labels) == {"2023-01", "2023-03"}
    assert labels["2023-01"].count == 2
    assert labels["2023-03"].count == 1
    assert limited.total_mentions == sum(bucket.count for bucket in limited.buckets)


def test_get_verse_timeline_rejects_invalid_window(tmp_path) -> None:
    engine = _prepare_engine(tmp_path)
    try:
        with Session(engine) as session:
            _seed_documents(session)

            with pytest.raises(ValueError):
                get_verse_timeline(session=session, osis="John.3.16", window="invalid")  # type: ignore[arg-type]
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_get_verse_timeline_filters_by_author_for_week_window(tmp_path) -> None:
    engine = _prepare_engine(tmp_path)
    try:
        with Session(engine) as session:
            documents = [
                Document(
                    id="multi-1",
                    title="Week One",
                    source_type="pdf",
                    authors=["Alice", "Bob"],
                    pub_date=date(2023, 1, 2),
                ),
                Document(
                    id="multi-2",
                    title="Week Two",
                    source_type="pdf",
                    authors=["Bob"],
                    pub_date=date(2023, 1, 9),
                ),
                Document(
                    id="multi-3",
                    title="Week Three",
                    source_type="pdf",
                    authors=["Alice"],
                    pub_date=date(2023, 1, 16),
                ),
            ]

            session.add_all(documents)
            session.flush()

            john_ids = list(sorted(expand_osis_reference("John.3.16")))

            passages = [
                Passage(
                    id="multi-p1",
                    document_id="multi-1",
                    text="Ref",
                    osis_ref="John.3.16",
                    osis_verse_ids=john_ids,
                ),
                Passage(
                    id="multi-p2",
                    document_id="multi-2",
                    text="Ref",
                    osis_ref="John.3.16",
                    osis_verse_ids=john_ids,
                ),
                Passage(
                    id="multi-p3",
                    document_id="multi-3",
                    text="Ref",
                    osis_ref="John.3.16",
                    osis_verse_ids=john_ids,
                ),
            ]
            session.add_all(passages)
            session.add_all(
                [
                    PassageVerse(passage_id=passage.id, verse_id=verse_id)
                    for passage in passages
                    for verse_id in john_ids
                ]
            )
            session.commit()

            timeline = get_verse_timeline(
                session=session,
                osis="John.3.16",
                window="week",
                filters=VerseMentionsFilters(author="Alice"),
            )
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]

    assert timeline.window == "week"
    assert timeline.total_mentions == 2

    labels = {bucket.label: bucket for bucket in timeline.buckets}
    assert sorted(labels.keys()) == ["2023-W01", "2023-W03"]

    first_week = labels["2023-W01"]
    assert first_week.count == 1
    assert first_week.document_ids == ["multi-1"]

    third_week = labels["2023-W03"]
    assert third_week.count == 1
    assert third_week.document_ids == ["multi-3"]

    assert all("multi-2" not in bucket.document_ids for bucket in timeline.buckets)
