from __future__ import annotations

from theo.infrastructure.api.app.models.search import HybridSearchResult
from theo.infrastructure.api.app.retriever import hybrid


def _result(result_id: str, document_id: str, score: float) -> HybridSearchResult:
    return HybridSearchResult(
        id=result_id,
        document_id=document_id,
        text=f"passage {result_id}",
        raw_text=None,
        osis_ref=None,
        start_char=None,
        end_char=None,
        page_no=None,
        t_start=None,
        t_end=None,
        score=score,
        meta=None,
        document_title=f"Document {document_id}",
        snippet="snippet",
        rank=0,
    )


def test_apply_document_ranks_orders_by_document_scores():
    results = [
        _result("p1", "doc1", 0.3),
        _result("p2", "doc1", 0.6),
        _result("p3", "doc2", 0.5),
    ]
    doc_scores = {"doc1": 0.6, "doc2": 0.5}
    tokens = ["passage"]

    ranked = hybrid._apply_document_ranks(results, doc_scores, tokens)

    assert ranked[0].document_rank == 1
    assert ranked[0].document_score == 0.6
    assert ranked[1].document_rank == 1
    assert ranked[2].document_rank == 2
    assert ranked[0].highlights
    assert ranked[1].highlights
