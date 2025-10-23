from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from hypothesis import given, settings, strategies as st

from theo.services.api.app.models.documents import DocumentAnnotationResponse
from theo.services.api.app.models.search import (
    HybridSearchFilters,
    HybridSearchRequest,
    HybridSearchResult,
)
from theo.services.api.app.retriever import hybrid


HYPOTHESIS_SETTINGS = settings(max_examples=40, deadline=None)

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


def test_tokenise_and_lexical_score_casefold_inputs():
    tokens = hybrid._tokenise(" Grace   ABOUNDS   \t   ")
    assert tokens == ["grace", "abounds"]

    score = hybrid._lexical_score("Grace abounds. Grace teaches.", ["grace", "teaches"])
    assert score == 3.0


def test_snippet_truncates_with_ellipsis():
    text = "x" * 300
    snippet = hybrid._snippet(text, max_length=50)

    assert snippet.endswith("...")
    assert len(snippet) == 50


def test_build_result_merges_meta_and_annotations(monkeypatch):
    passage = SimpleNamespace(
        id="p-meta",
        document_id="doc-meta",
        text="A" * 300,
        raw_text="A" * 300,
        osis_ref="Gen.1.1",
        start_char=0,
        end_char=300,
        page_no=2,
        t_start=1.5,
        t_end=5.5,
        meta={"existing": "value"},
    )
    document = SimpleNamespace(title="Doc Title")
    monkeypatch.setattr(hybrid, "compose_passage_meta", lambda *_args, **_kwargs: {"base": "meta"})

    timestamp = datetime(2024, 2, 1, tzinfo=UTC)
    annotation = DocumentAnnotationResponse(
        id="ann-meta",
        document_id="doc-meta",
        type="note",
        body="Important note",
        passage_ids=["p-meta"],
        created_at=timestamp,
        updated_at=timestamp,
    )

    result = hybrid._build_result(
        passage,
        document,
        [annotation],
        score=1.5,
        lexical_score=0.4,
        vector_score=0.8,
        osis_distance=0.0,
    )

    assert result.score == 1.5
    assert result.lexical_score == 0.4
    assert result.vector_score == 0.8
    assert result.snippet.endswith("...")
    assert result.meta is not None
    assert result.meta["base"] == "meta"
    assert result.meta["annotations"][0]["body"] == "Important note"


def test_apply_document_ranks_assigns_scores_and_highlights():
    results = [
        HybridSearchResult(
            id="p-1",
            document_id="doc-1",
            text="Grace teaches love and mercy.",
            raw_text="Grace teaches love and mercy.",
            osis_ref=None,
            start_char=0,
            end_char=30,
            page_no=None,
            t_start=None,
            t_end=None,
            score=0.9,
            meta=None,
            document_title="Doc One",
            snippet="Grace teaches love and mercy.",
            rank=0,
            highlights=None,
            lexical_score=0.6,
            vector_score=0.3,
            osis_distance=None,
        ),
        HybridSearchResult(
            id="p-2",
            document_id="doc-2",
            text="Hope anchors the soul.",
            raw_text="Hope anchors the soul.",
            osis_ref=None,
            start_char=0,
            end_char=24,
            page_no=None,
            t_start=None,
            t_end=None,
            score=0.4,
            meta=None,
            document_title="Doc Two",
            snippet="Hope anchors the soul.",
            rank=0,
            highlights=None,
            lexical_score=0.2,
            vector_score=0.1,
            osis_distance=None,
        ),
    ]

    updated = hybrid._apply_document_ranks(
        results,
        {"doc-1": 0.9, "doc-2": 0.4},
        ["grace"],
    )

    assert updated is results
    assert [res.document_rank for res in updated] == [1, 2]
    assert [res.document_score for res in updated] == [0.9, 0.4]
    assert updated[0].highlights and "Grace" in updated[0].highlights[0]
    assert updated[1].highlights == []


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


_TOPIC_TEXT = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=("Cs",)),
    min_size=1,
    max_size=32,
).filter(lambda value: value.strip() != "")


def _whitespace() -> st.SearchStrategy[str]:
    return st.text(alphabet=st.sampled_from([" ", "\t", "\n"]), min_size=0, max_size=3)


_ASCII_LOWER = st.characters(min_codepoint=97, max_codepoint=122)
_TOKEN = st.text(alphabet=_ASCII_LOWER, min_size=1, max_size=6)
_VALUE = st.one_of(_TOKEN, st.integers(min_value=-5, max_value=5), st.none())
_KEY = st.text(alphabet=_ASCII_LOWER, min_size=1, max_size=6)
_LIST_VALUE = st.lists(_VALUE, max_size=3)
_NESTED_DICT = st.lists(st.tuples(_KEY, _VALUE), max_size=2).map(dict)


@st.composite
def _tei_meta_dict(draw) -> dict[str, object]:
    entries = draw(
        st.lists(
            st.tuples(_KEY, st.one_of(_LIST_VALUE, _NESTED_DICT, _VALUE)),
            max_size=3,
        ).map(dict)
    )
    search_blob = draw(
        st.one_of(st.none(), st.lists(_TOKEN, max_size=4).map(" ".join))
    )
    meta: dict[str, object] = {}
    if entries:
        meta["tei"] = entries
    if search_blob is not None:
        meta["tei_search_blob"] = search_blob
    return meta


@st.composite
def _tei_meta_payload(draw) -> object:
    variant = draw(st.integers(min_value=0, max_value=2))
    if variant == 0:
        return draw(_tei_meta_dict())
    if variant == 1:
        return None
    return "unexpected"


def _expected_tei_terms(meta: object) -> list[str]:
    if not isinstance(meta, dict):
        return []
    terms: list[str] = []
    tei_section = meta.get("tei")
    if isinstance(tei_section, dict):
        for values in tei_section.values():
            if isinstance(values, list):
                terms.extend(str(value) for value in values)
            elif isinstance(values, dict):
                terms.extend(str(value) for value in values.values())
    search_blob = meta.get("tei_search_blob")
    if isinstance(search_blob, str):
        terms.extend(search_blob.split())
    return [term for term in terms if term]


@st.composite
def _query_tokens(draw) -> list[str]:
    return draw(st.lists(_TOKEN.map(str.lower), max_size=4))


@HYPOTHESIS_SETTINGS
@given(meta=_tei_meta_payload(), tokens=_query_tokens())
def test_tei_terms_and_match_score_property(meta: object, tokens: list[str]) -> None:
    passage = _make_passage(meta=meta)
    expected_terms = _expected_tei_terms(meta)

    assert hybrid._tei_terms(passage) == expected_terms

    lowered_terms = " ".join(term.lower() for term in expected_terms)
    expected_score = sum(lowered_terms.count(token) for token in tokens)
    assert hybrid._tei_match_score(passage, tokens) == pytest.approx(expected_score)


@HYPOTHESIS_SETTINGS
@given(
    base=_TOPIC_TEXT,
    extra_domains=st.lists(st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=("Cs",)), max_size=16), max_size=4),
    doc_prefix=_whitespace(),
    doc_suffix=_whitespace(),
    filter_prefix=_whitespace(),
    filter_suffix=_whitespace(),
)
def test_matches_topic_domain_handles_whitespace_and_casefold(
    base: str,
    extra_domains: list[str],
    doc_prefix: str,
    doc_suffix: str,
    filter_prefix: str,
    filter_suffix: str,
) -> None:
    document = _make_document(
        topic_domains=[*extra_domains, f"{doc_prefix}{base.swapcase()}{doc_suffix}"],
    )
    filter_value = f"{filter_prefix}{base}{filter_suffix}".upper()

    assert hybrid._matches_topic_domain(document, filter_value) is True


@st.composite
def _base_and_nonmatching_domains(draw):
    base = draw(_TOPIC_TEXT)
    normalized = base.strip().casefold()
    candidate = st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=("Cs",)),
        max_size=16,
    )
    others = draw(
        st.lists(candidate.filter(lambda value: not value.strip() or value.strip().casefold() != normalized), max_size=5)
    )
    return base, others


@HYPOTHESIS_SETTINGS
@given(_base_and_nonmatching_domains())
def test_matches_topic_domain_requires_normalised_match(data) -> None:
    base, other_domains = data
    document = _make_document(topic_domains=other_domains)
    filter_value = f" {base} "

    assert hybrid._matches_topic_domain(document, filter_value) is False


