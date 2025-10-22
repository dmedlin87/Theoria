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
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from theo.services.api.app.models.documents import DocumentAnnotationResponse
from theo.services.api.app.models.search import HybridSearchFilters, HybridSearchRequest
from theo.services.api.app.retriever import hybrid


def _make_document(**overrides):
    base = {
        "id": "doc-1",
        "title": "Grace Explored",
        "source_type": "sermon",
        "collection": "research",
        "authors": ["Alice"],
        "doi": "10.1234/example",
        "venue": "Theology Weekly",
        "year": 2024,
        "source_url": "https://example.com",
        "topics": ["Grace"],
        "theological_tradition": "Reformed",
        "topic_domains": ["Doctrine"],
        "enrichment_version": 2,
        "provenance_score": 5,
        "bib_json": {"primary_topic": "Grace"},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_passage(**overrides):
    base = {
        "id": "p1",
        "document_id": "doc-1",
        "text": "Grace teaches love and mercy in every heart.",
        "raw_text": "Grace teaches love",
        "osis_ref": "Gen.1.1",
        "start_char": 0,
        "end_char": 42,
        "page_no": 1,
        "t_start": None,
        "t_end": None,
        "meta": {
            "section": "introduction",
            "tei": {"keywords": ["Grace", "Mercy"], "extra": {"notes": ["Love"]}},
            "tei_search_blob": "Grace love hope",
        },
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_annotation_response(*, body: str, passage_ids: list[str] | None = None):
    passage_ids = passage_ids or []
    timestamp = datetime(2024, 1, 1, tzinfo=UTC)
    return DocumentAnnotationResponse(
        id="ann-1",
        document_id="doc-1",
        type="note",
        body=body,
        passage_ids=passage_ids,
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_build_highlights_limits_unique_clips():
    text = "Grace is abundant. Grace changes lives. Love flows from grace."
    tokens = ["grace", "love"]

    clips = hybrid._build_highlights(text, tokens, window=20, max_highlights=2)

    assert len(clips) == 2
    assert clips[0].startswith("Grace is abundant")
    assert "Grace changes" in clips[1]


def test_score_candidates_combines_vector_lexical_tei_and_annotations():
    document = _make_document()
    passage = _make_passage()
    candidate = hybrid._Candidate(passage=passage, document=document, vector_score=0.4, lexical_score=0.5)
    annotations = {
        passage.id: [_make_annotation_response(body="Grace filled note")],
    }
    request = HybridSearchRequest(query="Grace love", k=5)
    query_tokens = ["grace", "love"]

    scored = hybrid._score_candidates({passage.id: candidate}, annotations, request, query_tokens)

    assert len(scored) == 1
    result, score = scored[0]
    # Vector, lexical, annotation lexical bonus, and TEI score should all contribute.
    assert pytest.approx(score, rel=1e-6) == pytest.approx(result.score, rel=1e-6)
    assert score > 1.0
    assert result.lexical_score == 0.5
    assert result.vector_score == 0.4
    assert result.meta["annotations"][0]["body"] == "Grace filled note"


def test_score_candidates_skips_zero_scored_entries_when_query_present():
    document = _make_document()
    passage = _make_passage(meta={})
    candidate = hybrid._Candidate(passage=passage, document=document)
    request = HybridSearchRequest(query="Grace", k=3)
    query_tokens = ["grace"]

    scored = hybrid._score_candidates({passage.id: candidate}, {}, request, query_tokens)

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
def test_score_candidates_applies_osis_bonus_and_minimum_floor(monkeypatch):
    document = _make_document(id="doc-osis")
    passage = _make_passage(id="p-osis", osis_ref="Gen.1.1", meta={})
    candidate = hybrid._Candidate(passage=passage, document=document)
    request = HybridSearchRequest(query=None, osis="Gen.1.1", k=2)

    monkeypatch.setattr(hybrid, "expand_osis_reference", lambda value: {1})
    monkeypatch.setattr(hybrid, "osis_intersects", lambda candidate, target: True)

    hybrid._mark_candidate_osis(candidate, request.osis)  # type: ignore[arg-type]
    scored = hybrid._score_candidates({passage.id: candidate}, {}, request, [])

    assert len(scored) == 1
    result, score = scored[0]
    assert candidate.osis_match is True
    assert score == pytest.approx(0.3)
    assert result.osis_distance == 0.0


def test_merge_scored_candidates_assigns_ranks_and_document_scores():
    document_one = _make_document(id="doc-1", title="Primary")
    document_two = _make_document(id="doc-2", title="Secondary")
    passage_one = _make_passage(id="p1", document_id="doc-1")
    passage_two = _make_passage(id="p2", document_id="doc-2")
    annotations: dict[str, list[DocumentAnnotationResponse]] = {}
    request = HybridSearchRequest(query="Grace", k=2)
    query_tokens = ["grace"]

    candidates = {
        "p1": hybrid._Candidate(passage=passage_one, document=document_one, vector_score=0.6, lexical_score=0.4),
        "p2": hybrid._Candidate(passage=passage_two, document=document_two, vector_score=0.2, lexical_score=0.3),
    }

    scored = hybrid._score_candidates(candidates, annotations, request, query_tokens)
    merged = hybrid._merge_scored_candidates(scored, request, query_tokens)

    assert [result.rank for result in merged] == [1, 2]
    assert merged[0].document_rank == 1
    assert merged[1].document_rank == 2
    assert all(result.highlights for result in merged)


def test_osis_distance_value_prefers_nearest_reference(monkeypatch):
    def _fake_expand(value: str | None):
        mapping = {
            "Gen.1.1": {1, 5},
            "Gen.1.5": {5},
            "Gen.1.10": {10},
        }
        return mapping.get(value, set()) if value else set()

    monkeypatch.setattr(hybrid, "expand_osis_reference", _fake_expand)
    assert hybrid._osis_distance_value("Gen.1.1", "Gen.1.5") == 0.0
    assert hybrid._osis_distance_value("Gen.1.10", "Gen.1.5") == 5.0
    assert hybrid._osis_distance_value(None, "Gen.1.5") is None


def test_passes_author_and_guardrail_filters():
    document = _make_document(authors=["Alice", "Bob"], theological_tradition="Catholic", topic_domains=["Ethics"])  # type: ignore[arg-type]

    assert hybrid._passes_author_filter(document, "Alice") is True
    assert hybrid._passes_author_filter(document, "Charlie") is False

    assert hybrid._matches_tradition(document, " catholic ") is True
    assert hybrid._matches_tradition(document, "protestant") is False

    assert hybrid._matches_topic_domain(document, " ethics ") is True
    assert hybrid._matches_topic_domain(document, "doctrine") is False

    filters = HybridSearchFilters(theological_tradition="catholic", topic_domain="ethics")
    assert hybrid._passes_guardrail_filters(document, filters) is True

    filters = HybridSearchFilters(theological_tradition="reformed", topic_domain="ethics")
    assert hybrid._passes_guardrail_filters(document, filters) is False


def test_tei_terms_and_match_score():
    passage = _make_passage(
        meta={
            "tei": {
                "keywords": ["Grace", "Mercy"],
                "nested": {"notes": "Love"},
            },
            "tei_search_blob": "Grace mercy justice",
        }
    )
    terms = hybrid._tei_terms(passage)
    assert terms.count("Grace") == 2
    assert terms.count("Mercy") == 1
    assert terms.count("Love") == 1
    assert "justice" in terms

    score = hybrid._tei_match_score(passage, ["grace", "justice"])
    assert score == pytest.approx(3.0)
 

def test_build_statements_apply_filters_and_limits(monkeypatch):
    request = HybridSearchRequest(
        query="Grace",
        filters=HybridSearchFilters(collection="research", source_type="sermon"),
        k=3,
    )
    base_stmt = hybrid._build_base_query(request)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    dialect = engine.dialect

    from sqlalchemy.sql.elements import BinaryExpression

    monkeypatch.setattr(
        BinaryExpression,
        "astext",
        property(lambda self: self),
        raising=False,
    )

    vector_stmt = hybrid._build_vector_statement(base_stmt, [0.1, 0.2], limit=5, embedding_dim=2)
    lexical_stmt = hybrid._build_lexical_statement(base_stmt, request, limit=5)
    tei_stmt = hybrid._build_tei_statement(base_stmt, ["grace"], limit=5)

    compiled_vector = vector_stmt.compile(dialect=dialect)
    compiled_lexical = lexical_stmt.compile(dialect=dialect)
    compiled_tei = tei_stmt.compile(dialect=dialect)

    assert "cosine_distance" in str(compiled_vector)
    assert "ts_rank_cd" in str(compiled_lexical)
    assert any(value == 5 for value in compiled_vector.params.values())
    assert compiled_vector.params["collection_1"] == "research"
    assert compiled_vector.params["source_type_1"] == "sermon"
    assert any(value == 5 for value in compiled_lexical.params.values())
    assert any(str(value) == "%grace%" for value in compiled_tei.params.values())

