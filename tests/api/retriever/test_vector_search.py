from __future__ import annotations

from datetime import UTC, datetime

from theo.services.api.app.models.documents import DocumentAnnotationResponse
from theo.services.api.app.models.search import HybridSearchRequest
from theo.services.api.app.retriever import hybrid

from tests.api.retriever.conftest import DummyDocument, DummyPassage


def test_score_candidates_combines_signals():
    passage = DummyPassage(
        id="p1",
        document_id="d1",
        text="Faith works through love",
        osis_ref="Gen.1.1",
    )
    document = DummyDocument(
        id="d1",
        title="Document of Faith",
        authors=["Paul"],
    )
    candidate = hybrid._Candidate(passage=passage, document=document)
    candidate.vector_score = 0.8
    candidate.lexical_score = 0.4

    annotation = DocumentAnnotationResponse(
        id="a1",
        document_id="d1",
        type="note",
        body="Faith, hope, and love",
        stance=None,
        passage_ids=["p1"],
        group_id=None,
        metadata=None,
        raw=None,
        legacy=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    request = HybridSearchRequest(query="faith love", k=5)
    query_tokens = hybrid._tokenise(request.query or "")
    annotations_by_passage = {"p1": [annotation]}

    scored = hybrid._score_candidates(
        {"p1": candidate}, annotations_by_passage, request, query_tokens
    )

    assert scored
    result, score = scored[0]
    assert result.vector_score == candidate.vector_score
    assert result.lexical_score == candidate.lexical_score
    # Annotation content contributes additional lexical signal
    assert score > candidate.vector_score * 0.65 + candidate.lexical_score * 0.35
    assert "annotations" in (result.meta or {})
