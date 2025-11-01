import math
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from theo.infrastructure.api.app.models.documents import DocumentAnnotationResponse
from theo.infrastructure.api.app.models.search import (
    HybridSearchFilters,
    HybridSearchRequest,
    HybridSearchResult,
)
from theo.infrastructure.api.app.retriever import hybrid
from theo.infrastructure.api.app.retriever.hybrid import _Candidate


@pytest.fixture
def base_document():
    return SimpleNamespace(
        id="doc-1",
        title="Test Doc",
        source_type="sermon",
        collection="research",
        authors=["Tester"],
        doi=None,
        venue=None,
        year=2024,
        source_url=None,
        topics=["Grace"],
        theological_tradition="Catholic",
        topic_domains=["Ethics"],
        enrichment_version=1,
        provenance_score=0.9,
        bib_json={"primary_topic": "Grace"},
    )


@pytest.fixture
def base_passage(base_document):
    return SimpleNamespace(
        id="p-1",
        document_id=base_document.id,
        text="Grace and love abound in grace",
        raw_text="Grace and love abound in grace",
        osis_ref="Gen.1.1",
        start_char=0,
        end_char=33,
        page_no=1,
        t_start=None,
        t_end=None,
        meta={
            "tei": {"keywords": ["Grace", "Love"]},
            "tei_search_blob": "Grace love hope",
        },
    )


def _make_annotation(document_id: str, passage_id: str, body: str) -> DocumentAnnotationResponse:
    return DocumentAnnotationResponse(
        id="ann-1",
        document_id=document_id,
        type="note",
        body=body,
        passage_ids=[passage_id],
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def test_tokenise_normalises_and_discards_empty_tokens():
    assert hybrid._tokenise("  Grace   AND   Mercy  ") == ["grace", "and", "mercy"]
    assert hybrid._tokenise("   ") == []


@pytest.mark.parametrize(
    "text, tokens, expected",
    [
        ("Grace is grace", ["grace"], 2.0),
        ("Mercy", ["grace"], 0.0),
        ("", [], 0.0),
    ],
)
def test_lexical_score_counts_matches(text, tokens, expected):
    assert hybrid._lexical_score(text, tokens) == expected


def test_build_highlights_returns_unique_clipped_snippets():
    text = "Grace abounds. Another grace insight appears. Final grace reflection."
    highlights = hybrid._build_highlights(
        text,
        ["grace"],
        window=40,
        max_highlights=2,
    )
    assert len(highlights) == 2
    # Ensure highlights preserve ordering and contain query token
    assert highlights[0].lower().startswith("grace")
    assert "grace" in highlights[1].lower()


def test_calculate_candidate_score_combines_all_signals(base_document, base_passage):
    request = HybridSearchRequest(query="Grace love", osis="Gen.1.1", k=5)
    query_tokens = hybrid._tokenise(request.query or "")

    candidate = _Candidate(
        passage=base_passage,
        document=base_document,
        vector_score=0.8,
        lexical_score=0.5,
        osis_match=True,
        osis_distance=0.0,
    )

    annotations = [_make_annotation(base_document.id, base_passage.id, "Grace love note")]
    score = hybrid._calculate_candidate_score(
        candidate,
        request,
        query_tokens,
        annotations,
    )

    assert score is not None
    # Expected score: weighted vector + weighted lexical + annotation bonus + tei bonus + osis bonus
    expected = (0.65 * 0.8) + (0.35 * 0.5)
    expected += 0.35 * hybrid._lexical_score("Grace love note", query_tokens)
    expected += 0.35 * hybrid._tei_match_score(base_passage, query_tokens)
    expected += 0.2
    assert math.isclose(score, expected, rel_tol=1e-6)


def test_calculate_candidate_score_filters_irrelevant_results(base_document, base_passage):
    request = HybridSearchRequest(query="Grace", osis=None, k=5)
    query_tokens = hybrid._tokenise(request.query or "")

    empty_passage = SimpleNamespace(**{**base_passage.__dict__, "meta": {}})
    candidate = _Candidate(
        passage=empty_passage,
        document=base_document,
        vector_score=0.0,
        lexical_score=0.0,
        osis_match=False,
        osis_distance=None,
    )

    score = hybrid._calculate_candidate_score(
        candidate,
        request,
        query_tokens,
        [],
    )
    assert score is None


def test_merge_scored_candidates_assigns_ranks_and_highlights(base_document, base_passage):
    request = HybridSearchRequest(query="Grace", filters=HybridSearchFilters(), k=2)
    query_tokens = hybrid._tokenise(request.query or "")

    result1 = HybridSearchResult(
        id=base_passage.id,
        document_id=base_document.id,
        text=base_passage.text,
        raw_text=base_passage.raw_text,
        osis_ref=base_passage.osis_ref,
        start_char=0,
        end_char=len(base_passage.text),
        page_no=1,
        t_start=None,
        t_end=None,
        score=0.0,
        meta=None,
        document_title=base_document.title,
        snippet="Grace abounds",
        rank=0,
        highlights=None,
        lexical_score=0.5,
        vector_score=0.7,
        osis_distance=0.0,
    )
    result2 = HybridSearchResult(
        id="p-2",
        document_id="doc-2",
        text="Mercy speaks of grace",
        raw_text="Mercy speaks of grace",
        osis_ref=None,
        start_char=0,
        end_char=22,
        page_no=1,
        t_start=None,
        t_end=None,
        score=0.0,
        meta=None,
        document_title="Second Doc",
        snippet="Mercy speaks",
        rank=0,
        highlights=None,
        lexical_score=0.2,
        vector_score=0.4,
        osis_distance=None,
    )

    scored = [(result1, 0.9), (result2, 0.6)]
    merged = hybrid._merge_scored_candidates(scored, request, query_tokens)

    assert [res.rank for res in merged] == [1, 2]
    assert [res.document_rank for res in merged] == [1, 2]
    assert merged[0].document_id == base_document.id
    assert merged[0].highlights is not None
    assert any("grace" in highlight.lower() for highlight in merged[0].highlights)
