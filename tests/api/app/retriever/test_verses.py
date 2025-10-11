from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path
import sys

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core import database as database_module  # noqa: E402
from theo.services.api.app.core.database import (  # noqa: E402  # import after path tweak
    Base,
    configure_engine,
    get_engine,
)
from theo.services.api.app.db.models import Document, Passage  # noqa: E402
from theo.services.api.app.ingest.osis import expand_osis_reference  # noqa: E402
from theo.services.api.app.models.verses import VerseMentionsFilters  # noqa: E402
from theo.services.api.app.retriever.verses import (  # noqa: E402
    get_mentions_for_osis,
    get_verse_timeline,
)


def _prepare_engine(tmp_path: Path):
    configure_engine(f"sqlite:///{tmp_path / 'verses.db'}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def _session(tmp_path: Path):
    engine = _prepare_engine(tmp_path)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def _ids_and_bounds(osis: str) -> tuple[list[int], int, int]:
    ids = list(sorted(expand_osis_reference(osis)))
    return ids, ids[0], ids[-1]


def test_get_mentions_for_osis_uses_verse_ids(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        doc_hit = Document(
            id="doc-hit",
            title="Target",  # ensures meta composition remains intact
            source_type="pdf",
        )
        doc_range = Document(
            id="doc-range",
            title="Range",  # should also be included
            source_type="pdf",
        )
        doc_miss = Document(
            id="doc-miss",
            title="Miss",  # should be filtered out
            source_type="pdf",
        )
        session.add_all([doc_hit, doc_range, doc_miss])
        session.flush()

        john_316_ids, john_316_start, john_316_end = _ids_and_bounds("John.3.16")
        john_317_ids, john_317_start, john_317_end = _ids_and_bounds("John.3.17")
        john_range_ids, john_range_start, john_range_end = _ids_and_bounds(
            "John.3.16-John.3.17"
        )

        passages = [
            Passage(
                id="passage-hit",
                document_id=doc_hit.id,
                text="Primary hit",
                osis_ref=None,
                osis_verse_ids=john_316_ids,
                osis_start_verse_id=john_316_start,
                osis_end_verse_id=john_316_end,
            ),
            Passage(
                id="passage-range",
                document_id=doc_range.id,
                text="Range hit",
                osis_ref="John.3.16-John.3.17",
                osis_verse_ids=john_range_ids,
                osis_start_verse_id=john_range_start,
                osis_end_verse_id=john_range_end,
            ),
            Passage(
                id="passage-miss",
                document_id=doc_miss.id,
                text="Mismatched ids",
                osis_ref="John.3.16",  # legacy metadata but wrong ids
                osis_verse_ids=john_317_ids,
                osis_start_verse_id=john_317_start,
                osis_end_verse_id=john_317_end,
            ),
        ]
        session.add_all(passages)
        session.commit()

        mentions = get_mentions_for_osis(
            session=session,
            osis="John.3.16",
            filters=VerseMentionsFilters(),
        )

    returned_ids = {mention.passage.id for mention in mentions}
    assert returned_ids == {"passage-hit", "passage-range"}
    assert all(mention.context_snippet for mention in mentions)
    assert {
        mention.passage.meta["document_title"] for mention in mentions if mention.passage.meta
    } == {"Target", "Range"}


def test_get_mentions_for_osis_respects_filters(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        doc_primary = Document(
            id="doc-primary",
            title="Primary Collection",
            source_type="pdf",
            collection="Sermons",
            authors=["Alice", "Bob"],
        )
        doc_secondary = Document(
            id="doc-secondary",
            title="Secondary",
            source_type="pdf",
            collection="Sermons",
            authors=["Carol"],
        )
        doc_other_collection = Document(
            id="doc-other",
            title="Different Collection",
            source_type="pdf",
            collection="Notes",
            authors=["Alice"],
        )
        session.add_all([doc_primary, doc_secondary, doc_other_collection])
        session.flush()

        john_316_ids, john_316_start, john_316_end = _ids_and_bounds("John.3.16")

        session.add_all(
            [
                Passage(
                    id="primary-pass",
                    document_id=doc_primary.id,
                    text="Primary",
                    osis_ref="John.3.16",
                    osis_verse_ids=john_316_ids,
                    osis_start_verse_id=john_316_start,
                    osis_end_verse_id=john_316_end,
                ),
                Passage(
                    id="secondary-pass",
                    document_id=doc_secondary.id,
                    text="Secondary",
                    osis_ref="John.3.16",
                    osis_verse_ids=john_316_ids,
                    osis_start_verse_id=john_316_start,
                    osis_end_verse_id=john_316_end,
                ),
                Passage(
                    id="other-pass",
                    document_id=doc_other_collection.id,
                    text="Other",
                    osis_ref="John.3.16",
                    osis_verse_ids=john_316_ids,
                    osis_start_verse_id=john_316_start,
                    osis_end_verse_id=john_316_end,
                ),
            ]
        )
        session.commit()

        mentions = get_mentions_for_osis(
            session=session,
            osis="John.3.16",
            filters=VerseMentionsFilters(author="Alice", collection="Sermons"),
        )

    assert [mention.passage.id for mention in mentions] == ["primary-pass"]


def test_get_verse_timeline_uses_verse_ids(tmp_path: Path) -> None:
    with _session(tmp_path) as session:
        hit_doc = Document(
            id="timeline-hit",
            title="Timeline Hit",
            source_type="pdf",
            pub_date=date(2023, 1, 10),
        )
        miss_doc = Document(
            id="timeline-miss",
            title="Timeline Miss",
            source_type="pdf",
            pub_date=date(2023, 1, 12),
        )
        session.add_all([hit_doc, miss_doc])
        session.flush()

        john_316_ids, john_316_start, john_316_end = _ids_and_bounds("John.3.16")
        john_317_ids, john_317_start, john_317_end = _ids_and_bounds("John.3.17")

        session.add_all(
            [
                Passage(
                    id="timeline-hit-passage",
                    document_id=hit_doc.id,
                    text="Timeline target",
                    osis_ref="John.3.16",
                    osis_verse_ids=john_316_ids,
                    osis_start_verse_id=john_316_start,
                    osis_end_verse_id=john_316_end,
                ),
                Passage(
                    id="timeline-miss-passage",
                    document_id=miss_doc.id,
                    text="Timeline miss",
                    osis_ref="John.3.16",
                    osis_verse_ids=john_317_ids,
                    osis_start_verse_id=john_317_start,
                    osis_end_verse_id=john_317_end,
                ),
            ]
        )
        session.commit()

        response = get_verse_timeline(
            session=session,
            osis="John.3.16",
            window="month",
            filters=VerseMentionsFilters(),
        )

    assert response.total_mentions == 1
    assert len(response.buckets) == 1
    bucket = response.buckets[0]
    assert bucket.document_ids == ["timeline-hit"]
    assert bucket.sample_passage_ids == ["timeline-hit-passage"]
