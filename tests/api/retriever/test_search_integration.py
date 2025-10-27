from __future__ import annotations

from theo.infrastructure.api.app.models.search import HybridSearchRequest
from theo.infrastructure.api.app.retriever import hybrid

from tests.api.retriever.conftest import DummyDocument, DummyPassage


def test_merge_scored_candidates_prioritises_relevant_results():
    request = HybridSearchRequest(query="Grace and peace", osis="John.3.16", k=5)
    tokens = hybrid._tokenise(request.query or "")

    doc1 = DummyDocument(
        id="doc1",
        title="Grace Notes",
        theological_tradition="Reformed",
        topic_domains=["Doctrine"],
    )
    passage1 = DummyPassage(
        id="p1",
        document_id="doc1",
        text="Grace and peace be multiplied",
        osis_ref="John.3.16",
    )
    cand1 = hybrid._Candidate(passage=passage1, document=doc1)
    cand1.vector_score = 0.4
    cand1.lexical_score = 0.2
    hybrid._mark_candidate_osis(cand1, request.osis)

    doc2 = DummyDocument(
        id="doc2",
        title="Peace Studies",
        theological_tradition="Reformed",
        topic_domains=["Doctrine"],
    )
    passage2 = DummyPassage(
        id="p2",
        document_id="doc2",
        text="Peace like a river",
        osis_ref="John.3.14",
        meta={"tei_search_blob": "peace river"},
    )
    cand2 = hybrid._Candidate(passage=passage2, document=doc2)
    cand2.lexical_score = 0.7

    doc3 = DummyDocument(id="doc3", title="Irrelevant")
    passage3 = DummyPassage(id="p3", document_id="doc3", text="", osis_ref=None)
    cand3 = hybrid._Candidate(passage=passage3, document=doc3)

    scored = hybrid._score_candidates(
        {"p1": cand1, "p2": cand2, "p3": cand3}, {}, request, tokens
    )

    results = hybrid._merge_scored_candidates(scored, request, tokens)

    assert [result.id for result in results] == ["p2", "p1"]
    assert results[0].rank == 1
    assert results[1].rank == 2
    assert results[1].osis_distance == 0.0
    assert results[0].document_score >= results[1].document_score
