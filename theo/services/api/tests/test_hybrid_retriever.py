"""Tests for the hybrid retriever helper construction."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from theo.services.api.app.core.database import get_engine
from theo.services.api.app.db.models import Document, DocumentAnnotation, Passage
from theo.services.api.app.models.documents import DocumentAnnotationResponse
from theo.services.api.app.models.search import HybridSearchRequest
from theo.services.api.app.retriever.hybrid import (
    _Candidate,
    _fallback_search,
    _merge_scored_candidates,
    _score_candidates,
    _tokenise,
)


def _create_document_and_passage(document_id: str, passage_id: str) -> tuple[Document, Passage]:
    document = Document(
        id=document_id,
        title="Doctrine of Grace",
        source_type="test",
    )
    passage = Passage(
        id=passage_id,
        document_id=document_id,
        text="Grace and peace are multiplied to you.",
        raw_text="Grace and peace are multiplied to you.",
    )
    return document, passage


def test_score_candidates_serialises_annotations_and_highlights() -> None:
    document, passage = _create_document_and_passage(
        "doc-postgres", "passage-postgres"
    )

    annotation = DocumentAnnotationResponse(
        id="annotation-postgres",
        document_id=document.id,
        type="note",
        body="Grace annotation",
        stance=None,
        passage_ids=[passage.id],
        group_id=None,
        metadata=None,
        raw=None,
        legacy=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    request = HybridSearchRequest(query="Grace", k=5)
    query_tokens = _tokenise(request.query or "")

    candidate = _Candidate(
        passage=passage,
        document=document,
        vector_score=0.9,
        lexical_score=0.7,
    )

    scored = _score_candidates(
        {passage.id: candidate},
        {passage.id: [annotation]},
        request,
        query_tokens,
    )

    assert scored, "expected candidate to be scored"

    results = _merge_scored_candidates(scored, request, query_tokens)
    assert len(results) == 1

    result = results[0]
    annotations = result.meta and result.meta.get("annotations")
    assert annotations and annotations[0]["body"] == "Grace annotation"
    assert result.snippet == passage.text
    assert result.lexical_score == pytest.approx(0.7)
    assert result.vector_score == pytest.approx(0.9)
    assert result.highlights is not None and any(
        "grace" in snippet.lower() for snippet in result.highlights
    )


def test_fallback_search_preserves_annotations_and_highlights() -> None:
    engine = get_engine()
    with Session(engine) as session:
        document, passage = _create_document_and_passage(
            "doc-fallback", "passage-fallback"
        )
        annotation = DocumentAnnotation(
            id="annotation-fallback",
            document_id=document.id,
            body=json.dumps(
                {
                    "type": "note",
                    "text": "Fallback grace annotation",
                    "passage_ids": [passage.id],
                }
            ),
        )

        session.add_all([document, passage, annotation])
        session.commit()

        try:
            request = HybridSearchRequest(query="Grace", k=5)
            results = _fallback_search(session, request)

            assert len(results) == 1
            result = results[0]

            annotations = result.meta and result.meta.get("annotations")
            assert annotations and annotations[0]["body"] == "Fallback grace annotation"
            assert result.snippet == passage.text
            assert result.lexical_score is not None and result.lexical_score > 0
            assert result.highlights is not None and any(
                "grace" in snippet.lower() for snippet in result.highlights
            )
        finally:
            session.delete(annotation)
            session.delete(passage)
            session.delete(document)
            session.commit()
