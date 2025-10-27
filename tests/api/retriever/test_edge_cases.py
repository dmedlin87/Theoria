from __future__ import annotations

from theo.infrastructure.api.app.models.search import HybridSearchFilters
from theo.infrastructure.api.app.retriever import hybrid

from tests.api.retriever.conftest import DummyDocument, DummyPassage


def test_author_and_guardrail_filters():
    document = DummyDocument(
        id="doc",
        authors=["Paul"],
        theological_tradition="Reformed",
        topic_domains=["Ethics"],
    )
    filters = HybridSearchFilters(
        author="Paul", theological_tradition="reformed", topic_domain="ethics"
    )

    assert hybrid._passes_author_filter(document, filters.author)
    assert hybrid._passes_guardrail_filters(document, filters)

    document.authors = None
    assert not hybrid._passes_author_filter(document, filters.author)


def test_tradition_and_topic_matching_ignore_whitespace():
    document = DummyDocument(
        id="doc2",
        theological_tradition=" Anglican ",
        topic_domains=["Practical Theology"],
    )
    assert hybrid._matches_tradition(document, "anglican")
    assert hybrid._matches_topic_domain(document, "practical theology")


def test_osis_distance_and_marking():
    candidate = hybrid._Candidate(
        passage=DummyPassage(id="p1", document_id="d1", text="", osis_ref="John.3.14"),
        document=DummyDocument(id="d1"),
    )
    hybrid._mark_candidate_osis(candidate, "John.3.16")
    assert candidate.osis_match is True
    assert candidate.osis_distance is not None
    assert candidate.osis_distance >= 0.0

    assert (
        hybrid._osis_distance_value(
            DummyPassage(id="p-none", document_id="d1", text="", osis_ref=None), None
        )
        is None
    )
    assert (
        hybrid._osis_distance_value(
            DummyPassage(
                id="p-match",
                document_id="d1",
                text="",
                osis_ref="John.3.16",
                osis_start_verse_id=123456,
                osis_end_verse_id=123456,
            ),
            "John.3.16",
        )
        == 0.0
    )


def test_tei_term_extraction_handles_nested_meta():
    passage = DummyPassage(
        id="p2",
        document_id="d2",
        text="",
        meta={
            "tei": {"topics": ["Grace"], "extra": {"nested": "Hope"}},
            "tei_search_blob": "Faith Hope Love",
        },
    )
    tokens = hybrid._tokenise("grace hope")
    assert hybrid._tei_terms(passage)
    score = hybrid._tei_match_score(passage, tokens)
    assert score >= 2


def test_tokenise_handles_empty_text():
    assert hybrid._tokenise("") == []
