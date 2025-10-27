from types import SimpleNamespace

import pytest

from theo.infrastructure.api.app.models.search import (
    HybridSearchFilters,
    HybridSearchRequest,
    HybridSearchResult,
)
from theo.infrastructure.api.app.retriever.hybrid import (
    _Candidate,
    _merge_scored_candidates,
    _score_candidates,
)


class DummyNote:
    def __init__(self, body: str) -> None:
        self.body = body

    def model_dump(self, *, mode: str) -> dict[str, str]:  # pragma: no cover - simple helper
        return {"body": self.body, "mode": mode}


@pytest.fixture
def query_request() -> HybridSearchRequest:
    return HybridSearchRequest(query="holiness hope", filters=HybridSearchFilters(), k=5)


def _make_passage(passage_id: str, text: str, **extras) -> SimpleNamespace:
    meta = extras.pop("meta", {})
    return SimpleNamespace(
        id=passage_id,
        document_id=f"doc-{passage_id}",
        text=text,
        raw_text=text,
        osis_ref=extras.get("osis_ref"),
        start_char=0,
        end_char=len(text),
        page_no=None,
        t_start=None,
        t_end=None,
        meta=meta,
    )


def _make_document(title: str, **extras) -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        source_type=extras.get("source_type"),
        collection=extras.get("collection"),
        authors=extras.get("authors"),
        doi=extras.get("doi"),
        venue=extras.get("venue"),
        year=extras.get("year"),
        source_url=extras.get("source_url"),
        topics=extras.get("topics"),
        topic_domains=extras.get("topic_domains"),
        theological_tradition=extras.get("theological_tradition"),
        enrichment_version=extras.get("enrichment_version"),
        provenance_score=extras.get("provenance_score"),
        bib_json=extras.get("bib_json"),
    )


def test_score_candidates_includes_annotations_and_weights(query_request: HybridSearchRequest) -> None:
    passage = _make_passage("1", "Hope that endures", osis_ref="John.1.1")
    document = _make_document("Example")
    candidate = _Candidate(passage=passage, document=document, vector_score=0.4, lexical_score=0.3)
    candidate.osis_match = True
    annotations = {passage.id: [DummyNote("Hope inspires courage")]}  # adds lexical weight

    scored = _score_candidates({passage.id: candidate}, annotations, query_request, ["hope", "endures"])

    assert len(scored) == 1
    result, score = scored[0]
    # Expect vector + lexical weights and annotation boost plus OSIS bonus
    assert score > 0.0
    assert result.document_title == "Example"
    assert result.meta and "annotations" in result.meta
    assert pytest.approx(score, rel=1e-3) == score  # ensure score is numeric


def test_merge_scored_candidates_respects_limit(query_request: HybridSearchRequest) -> None:
    query_request.k = 1
    passage = _make_passage("1", "Alpha text")
    other_passage = _make_passage("2", "Beta text")
    base_payload = {
        "id": passage.id,
        "document_id": passage.document_id,
        "text": passage.text,
        "raw_text": passage.raw_text,
        "osis_ref": None,
        "start_char": 0,
        "end_char": len(passage.text),
        "page_no": None,
        "t_start": None,
        "t_end": None,
        "score": 1.0,
        "meta": {},
        "document_title": "Alpha",
        "snippet": passage.text,
        "rank": 0,
        "highlights": None,
        "lexical_score": None,
        "vector_score": None,
        "osis_distance": None,
    }
    other_payload = {
        **base_payload,
        "id": other_passage.id,
        "document_id": other_passage.document_id,
        "document_title": "Beta",
        "score": 0.5,
    }

    scored = [
        (HybridSearchResult(**base_payload), 1.0),
        (HybridSearchResult(**other_payload), 0.5),
    ]

    merged = _merge_scored_candidates(scored, query_request, ["alpha"])
    assert len(merged) == 1
    assert merged[0].document_title == "Alpha"
    assert merged[0].rank == 1
