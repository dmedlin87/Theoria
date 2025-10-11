from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from theo.services.api.app.core.database import get_engine
from theo.services.api.app.db.models import Document, Passage
from theo.services.api.app.ingest.osis import expand_osis_reference
from theo.services.api.app.models.verses import VerseMentionsFilters
from theo.services.api.app.retriever.verses import (
    get_mentions_for_osis,
    get_verse_timeline,
)


def _verse_range(reference: str) -> tuple[int, int]:
    verse_ids = expand_osis_reference(reference)
    assert verse_ids, "expected expand_osis_reference to return verse ids"
    return min(verse_ids), max(verse_ids)


def test_get_mentions_for_osis_filters_by_verse_range_and_metadata() -> None:
    engine = get_engine()
    with Session(engine) as session:
        doc_a = Document(
            id="doc-verse-a",
            title="First Doc",
            source_type="sermon",
            authors=["Alice"],
            collection="Sermons",
            pub_date=date(2024, 1, 1),
        )
        doc_b = Document(
            id="doc-verse-b",
            title="Second Doc",
            source_type="sermon",
            authors=["Bob"],
            collection="Lectures",
            pub_date=date(2024, 2, 1),
        )
        doc_c = Document(
            id="doc-verse-c",
            title="Third Doc",
            source_type="sermon",
            authors=["Alice"],
            collection="Lectures",
            pub_date=date(2024, 3, 1),
        )

        start_a, end_a = _verse_range("John.1.1-5")
        passage_range = Passage(
            id="passage-range",
            document_id=doc_a.id,
            text="In the beginning was the Word.",
            raw_text="In the beginning was the Word.",
            osis_ref="John.1.1-5",
            osis_start_verse_id=start_a,
            osis_end_verse_id=end_a,
            meta={"osis_refs_all": ["John.1.1-5"]},
        )

        passage_fallback = Passage(
            id="passage-fallback",
            document_id=doc_a.id,
            text="And the light shineth in darkness.",
            raw_text="And the light shineth in darkness.",
            osis_ref="John.1.4",
            meta={"osis_refs_all": ["John.1.4"]},
        )

        start_b, end_b = _verse_range("John.1.3-4")
        passage_other_author = Passage(
            id="passage-other-author",
            document_id=doc_b.id,
            text="John bore witness of him.",
            raw_text="John bore witness of him.",
            osis_ref="John.1.3-4",
            osis_start_verse_id=start_b,
            osis_end_verse_id=end_b,
            meta={"osis_refs_all": ["John.1.3-4"]},
        )

        start_c, end_c = _verse_range("John.3.16")
        passage_out_of_range = Passage(
            id="passage-out-of-range",
            document_id=doc_c.id,
            text="For God so loved the world.",
            raw_text="For God so loved the world.",
            osis_ref="John.3.16",
            osis_start_verse_id=start_c,
            osis_end_verse_id=end_c,
            meta={"osis_refs_all": ["John.3.16"]},
        )

        session.add_all(
            [
                doc_a,
                doc_b,
                doc_c,
                passage_range,
                passage_fallback,
                passage_other_author,
                passage_out_of_range,
            ]
        )
        session.commit()

        try:
            mentions = get_mentions_for_osis(session, "John.1.3-4")
            mention_ids = {item.passage.id for item in mentions}
            assert mention_ids == {
                passage_range.id,
                passage_fallback.id,
                passage_other_author.id,
            }

            filtered = get_mentions_for_osis(
                session,
                "John.1.3-4",
                VerseMentionsFilters(author="Alice"),
            )
            filtered_ids = {item.passage.id for item in filtered}
            assert filtered_ids == {passage_range.id, passage_fallback.id}

            collection_filtered = get_mentions_for_osis(
                session,
                "John.1.3-4",
                VerseMentionsFilters(collection="Lectures"),
            )
            collection_ids = {item.passage.id for item in collection_filtered}
            assert collection_ids == {passage_other_author.id}
        finally:
            for passage in (
                passage_out_of_range,
                passage_other_author,
                passage_fallback,
                passage_range,
            ):
                session.delete(passage)
            for document in (doc_c, doc_b, doc_a):
                session.delete(document)
            session.commit()


def test_get_verse_timeline_respects_filters_and_ranges() -> None:
    engine = get_engine()
    with Session(engine) as session:
        doc_a = Document(
            id="doc-timeline-a",
            title="Timeline A",
            source_type="sermon",
            authors=["Alice"],
            collection="Sermons",
            pub_date=date(2024, 1, 15),
        )
        doc_b = Document(
            id="doc-timeline-b",
            title="Timeline B",
            source_type="sermon",
            authors=["Bob"],
            collection="Lectures",
            pub_date=date(2024, 2, 20),
        )

        start_a, end_a = _verse_range("John.1.1-5")
        passage_a = Passage(
            id="passage-timeline-a",
            document_id=doc_a.id,
            text="Grace be with all them that love our Lord.",
            raw_text="Grace be with all them that love our Lord.",
            osis_ref="John.1.1-5",
            osis_start_verse_id=start_a,
            osis_end_verse_id=end_a,
            meta={"osis_refs_all": ["John.1.1-5"]},
        )

        start_b, end_b = _verse_range("John.1.3-4")
        passage_b = Passage(
            id="passage-timeline-b",
            document_id=doc_b.id,
            text="The same came for a witness.",
            raw_text="The same came for a witness.",
            osis_ref="John.1.3-4",
            osis_start_verse_id=start_b,
            osis_end_verse_id=end_b,
            meta={"osis_refs_all": ["John.1.3-4"]},
        )

        session.add_all([doc_a, doc_b, passage_a, passage_b])
        session.commit()

        try:
            timeline = get_verse_timeline(
                session,
                "John.1.3-4",
                filters=VerseMentionsFilters(author="Alice"),
            )
            assert timeline.total_mentions == 1
            assert timeline.buckets
            first_bucket = timeline.buckets[0]
            assert first_bucket.document_ids == [doc_a.id]
            assert first_bucket.count == 1

            lectures_timeline = get_verse_timeline(
                session,
                "John.1.3-4",
                filters=VerseMentionsFilters(collection="Lectures"),
            )
            assert lectures_timeline.total_mentions == 1
            assert lectures_timeline.buckets
            lecture_bucket = lectures_timeline.buckets[0]
            assert lecture_bucket.document_ids == [doc_b.id]
            assert lecture_bucket.count == 1
        finally:
            session.delete(passage_b)
            session.delete(passage_a)
            session.delete(doc_b)
            session.delete(doc_a)
            session.commit()
