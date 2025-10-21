"""Unit tests for the hybrid retriever helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from theo.services.api.app.models.documents import DocumentAnnotationResponse
from theo.services.api.app.models.search import (
    HybridSearchFilters,
    HybridSearchRequest,
)
from theo.services.api.app.retriever import hybrid


@dataclass
class DummyPassage:
    id: str
    document_id: str
    text: str
    raw_text: str | None = None
    osis_ref: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    page_no: int | None = None
    t_start: float | None = None
    t_end: float | None = None
    meta: dict | None = field(default_factory=dict)
    lexeme: str | None = None


@dataclass
class DummyDocument:
    id: str
    title: str
    authors: list[str] | None = None
    collection: str | None = None
    source_type: str | None = None
    theological_tradition: str | None = None
    topic_domains: list[str] | None = None
    topics: list[str] | None = None
    doi: str | None = None
    venue: str | None = None
    year: int | None = None
    source_url: str | None = None
    enrichment_version: int | None = None
    provenance_score: float | None = None
    bib_json: dict | None = None


def make_annotation(passage_id: str, body: str) -> DocumentAnnotationResponse:
    now = datetime.now(UTC)
    return DocumentAnnotationResponse(
        id=f"ann-{passage_id}",
        document_id="doc-1",
        type="note",
        body=body,
        stance=None,
        passage_ids=[passage_id],
        group_id=None,
        metadata=None,
        raw=None,
        legacy=False,
        created_at=now,
        updated_at=now,
    )


def test_tokenise_and_lexical_score_behaviour() -> None:
    tokens = hybrid._tokenise(" Grace and TRUTH \n")
    assert tokens == ["grace", "and", "truth"]

    score = hybrid._lexical_score("Grace upon grace and truth", tokens)
    # "grace" appears twice, "and" once, "truth" once.
    assert score == pytest.approx(4.0)


def test_snippet_and_highlights_limit_context() -> None:
    text = "Lorem ipsum dolor sit amet consectetur adipiscing elit"
    snippet = hybrid._snippet(text, max_length=20)
    assert snippet.endswith("...")
    assert len(snippet) <= 20

    highlights = hybrid._build_highlights(
        "alpha beta gamma alpha delta", ["alpha", "gamma"], window=12, max_highlights=2
    )
    assert len(highlights) == 2
    # Highlights should retain the matched tokens and avoid duplicates.
    assert highlights[0].strip().lower().startswith("alpha")
    assert len(set(highlights)) == len(highlights)


def test_build_result_merges_annotations_into_meta() -> None:
    passage = DummyPassage(
        id="p-1",
        document_id="doc-1",
        text="Alpha and omega",
        raw_text="Alpha and omega",
        meta={"passage": "meta"},
    )
    document = DummyDocument(id="doc-1", title="Doc One")
    annotations = [make_annotation("p-1", "alpha note")]

    result = hybrid._build_result(
        passage,
        document,
        annotations,
        score=1.0,
        lexical_score=0.4,
        vector_score=0.9,
        osis_distance=2.0,
    )

    assert result.meta["passage"] == "meta"
    assert result.meta["annotations"][0]["body"] == "alpha note"
    assert result.snippet.startswith("Alpha")
    assert result.lexical_score == 0.4
    assert result.vector_score == 0.9


def test_apply_document_ranks_sets_scores_and_highlights() -> None:
    passage = DummyPassage(
        id="p-1",
        document_id="doc-1",
        text="Alpha beta gamma",
        raw_text="Alpha beta gamma",
    )
    document = DummyDocument(id="doc-1", title="Doc")
    result = hybrid._build_result(
        passage,
        document,
        annotations=[],
        score=0.0,
        lexical_score=0.3,
        vector_score=0.5,
        osis_distance=None,
    )

    updated = hybrid._apply_document_ranks(
        [result],
        doc_scores={"doc-1": 0.75},
        query_tokens=["alpha"],
    )

    assert updated[0].document_rank == 1
    assert updated[0].document_score == 0.75
    assert updated[0].highlights == ["Alpha beta gamma"]


def test_score_candidates_combines_vector_lexical_and_annotation_scores() -> None:
    passage = DummyPassage(
        id="p-1",
        document_id="doc-1",
        text="Alpha beta",
        raw_text="Alpha beta",
        meta={"tei": {"keywords": ["Alpha"]}},
    )
    document = DummyDocument(id="doc-1", title="Doc")
    candidate = hybrid._Candidate(
        passage=passage,
        document=document,
        vector_score=0.8,
        lexical_score=0.5,
    )
    annotations = {"p-1": [make_annotation("p-1", "Alpha reference")]}

    request = HybridSearchRequest(query="Alpha")
    tokens = hybrid._tokenise(request.query)

    scored = hybrid._score_candidates(
        {"p-1": candidate},
        annotations,
        request,
        tokens,
    )

    assert len(scored) == 1
    result, score = scored[0]
    # Vector (0.8 * 0.65) + lexical (0.5 * 0.35) + annotation boost (1 * 0.35) + TEI (1 * 0.35)
    assert score == pytest.approx(1.395, rel=1e-5)
    assert result.lexical_score == 0.5
    assert result.vector_score == 0.8


def test_score_candidates_skips_zero_score_when_query_present() -> None:
    passage = DummyPassage(id="p-2", document_id="doc-2", text="", raw_text="")
    document = DummyDocument(id="doc-2", title="Doc Two")
    candidate = hybrid._Candidate(passage=passage, document=document)

    request = HybridSearchRequest(query="Alpha")
    tokens = hybrid._tokenise(request.query)

    scored = hybrid._score_candidates(
        {"p-2": candidate},
        annotations_by_passage={},
        request=request,
        query_tokens=tokens,
    )

    assert scored == []


def test_score_candidates_keeps_zero_scores_when_no_query() -> None:
    passage = DummyPassage(id="p-3", document_id="doc-3", text="", raw_text="")
    document = DummyDocument(id="doc-3", title="Doc Three")
    candidate = hybrid._Candidate(passage=passage, document=document)

    request = HybridSearchRequest(query=None)
    tokens: list[str] = []

    scored = hybrid._score_candidates(
        {"p-3": candidate},
        annotations_by_passage={},
        request=request,
        query_tokens=tokens,
    )

    assert scored[0][1] == pytest.approx(0.1)


def test_merge_scored_candidates_orders_and_assigns_ranks() -> None:
    request = HybridSearchRequest(query="alpha", k=2)
    tokens = hybrid._tokenise(request.query)

    doc = DummyDocument(id="doc-1", title="Doc")
    passage_a = DummyPassage(
        id="p-1",
        document_id="doc-1",
        text="Alpha beta",
        raw_text="Alpha beta",
    )
    passage_b = DummyPassage(
        id="p-2",
        document_id="doc-2",
        text="Alpha gamma",
        raw_text="Alpha gamma",
    )
    doc_b = DummyDocument(id="doc-2", title="Doc B")

    result_a = hybrid._build_result(
        passage_a,
        doc,
        annotations=[],
        score=0.0,
        lexical_score=0.2,
        vector_score=0.3,
        osis_distance=None,
    )
    result_b = hybrid._build_result(
        passage_b,
        doc_b,
        annotations=[],
        score=0.0,
        lexical_score=0.4,
        vector_score=0.1,
        osis_distance=None,
    )

    merged = hybrid._merge_scored_candidates(
        [(result_a, 0.6), (result_b, 0.9)],
        request,
        tokens,
    )

    assert [res.id for res in merged] == ["p-2", "p-1"]
    assert merged[0].rank == 1
    assert merged[0].document_rank == 1
    assert merged[1].document_rank == 2


def test_osis_distance_and_mark_candidate_updates_distance() -> None:
    distance = hybrid._osis_distance_value("Gen.1.1", "Gen.1.3")
    assert distance == pytest.approx(2.0)

    overlapping = hybrid._osis_distance_value("Gen.1.1", "Gen.1.1")
    assert overlapping == 0.0

    candidate = hybrid._Candidate(
        passage=DummyPassage(
            id="p-osis",
            document_id="doc",
            text="",
            raw_text="",
            osis_ref="Gen.1.5",
        ),
        document=DummyDocument(id="doc", title="Doc"),
    )
    hybrid._mark_candidate_osis(candidate, "Gen.1.4")
    assert candidate.osis_match is True
    assert candidate.osis_distance == pytest.approx(1.0)


def test_guardrail_filters_require_matching_tradition_and_domain() -> None:
    document = DummyDocument(
        id="doc",
        title="Doc",
        authors=["Author"],
        theological_tradition="Catholic",
        topic_domains=["History"],
    )
    filters = HybridSearchFilters(
        author="Author",
        theological_tradition="catholic",
        topic_domain="history",
    )

    assert hybrid._passes_author_filter(document, filters.author) is True
    assert hybrid._passes_guardrail_filters(document, filters) is True

    filters.topic_domain = "philosophy"
    assert hybrid._passes_guardrail_filters(document, filters) is False


def test_tei_terms_and_match_score_collect_nested_terms() -> None:
    passage = DummyPassage(
        id="p-tei",
        document_id="doc",
        text="",
        raw_text="",
        meta={
            "tei": {"sections": ["Alpha", "Beta"], "nested": {"more": "Gamma"}},
            "tei_search_blob": "Alpha delta",
        },
    )

    terms = hybrid._tei_terms(passage)
    assert sorted(terms) == ["Alpha", "Alpha", "Beta", "Gamma", "delta"]

    tokens = ["alpha", "gamma"]
    score = hybrid._tei_match_score(passage, tokens)
    # "alpha" appears twice (case-insensitive) and "gamma" once.
    assert score == pytest.approx(3.0)

