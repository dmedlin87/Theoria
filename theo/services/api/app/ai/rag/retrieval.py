"""Retrieval utilities used by RAG workflows."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from ...analytics.telemetry import record_feedback_event
from ...models.search import (
    HybridSearchFilters,
    HybridSearchRequest,
    HybridSearchResult,
)
from ...retriever.hybrid import hybrid_search
from .guardrail_helpers import load_passages_for_osis

if TYPE_CHECKING:  # pragma: no cover - hints only
    from ..trails import TrailRecorder
    from .models import RAGCitation


LOGGER = logging.getLogger(__name__)


class PassageRetriever:
    """Encapsulates passage lookup logic for reuse across workflows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        *,
        query: str | None,
        osis: str | None,
        filters: HybridSearchFilters,
        k: int = 8,
    ) -> list[HybridSearchResult]:
        request = HybridSearchRequest(query=query, osis=osis, filters=filters, k=k)
        results = list(hybrid_search(self._session, request))
        if osis and not any(result.osis_ref for result in results):
            fallback = load_passages_for_osis(self._session, osis)
            if fallback:
                LOGGER.debug(
                    "Hybrid search yielded no OSIS matches; injecting %d fallback passages for %s",
                    len(fallback),
                    osis,
                )
                return fallback
        return results


def search_passages(
    session: Session,
    *,
    query: str | None,
    osis: str | None,
    filters: HybridSearchFilters,
    k: int = 8,
) -> list[HybridSearchResult]:
    """Retrieve passages using the shared retrieval pipeline."""

    retriever = PassageRetriever(session)
    return retriever.search(query=query, osis=osis, filters=filters, k=k)


def record_used_citation_feedback(
    session: Session,
    *,
    citations: Sequence["RAGCitation"],
    results: Sequence[HybridSearchResult],
    query: str | None,
    recorder: "TrailRecorder | None" = None,
) -> None:
    """Persist feedback events indicating which passages were cited."""

    if not citations:
        return

    result_by_passage: dict[str, HybridSearchResult] = {
        str(result.id): result
        for result in results
        if getattr(result, "id", None)
    }
    user_id: str | None = None
    if recorder is not None and getattr(recorder, "trail", None) is not None:
        user_id = getattr(recorder.trail, "user_id", None)

    for citation in citations:
        passage_id = getattr(citation, "passage_id", None)
        document_id = getattr(citation, "document_id", None)
        if not passage_id and not document_id:
            continue
        context = result_by_passage.get(str(passage_id)) if passage_id else None
        record_feedback_event(
            session,
            action="used_in_answer",
            user_id=user_id,
            query=query,
            document_id=document_id,
            passage_id=passage_id,
            rank=getattr(context, "rank", getattr(citation, "index", None)),
            score=getattr(context, "score", None),
        )
__all__ = [
    "PassageRetriever",
    "record_used_citation_feedback",
    "search_passages",
]
