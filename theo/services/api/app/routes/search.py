"""Search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session
from ..ingest.embeddings import clear_embedding_cache
from ..models.search import (
    HybridSearchFilters,
    HybridSearchRequest,
    HybridSearchResponse,
)
from ..services.retrieval_service import (
    RetrievalService,
    get_retrieval_service,
    reset_reranker_cache as _reset_reranker_cache,
)

router = APIRouter()


def reset_reranker_cache() -> None:
    """Expose a reset hook for tests.

    Clears both reranker and embedding caches to minimise cross-test state.
    """

    _reset_reranker_cache()
    clear_embedding_cache()


@router.get("/", response_model=HybridSearchResponse)
def search(
    response: Response,
    q: str | None = Query(default=None, description="Keyword query"),
    osis: str | None = Query(default=None, description="Normalized OSIS reference"),
    collection: str | None = Query(
        default=None, description="Restrict to a collection"
    ),
    author: str | None = Query(default=None, description="Filter by author"),
    source_type: str | None = Query(
        default=None, description="Restrict to a source type"
    ),
    theological_tradition: str | None = Query(
        default=None,
        description="Restrict to documents aligned with a theological tradition",
    ),
    topic_domain: str | None = Query(
        default=None,
        description="Restrict to documents tagged with a topic domain",
    ),
    k: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> HybridSearchResponse:
    """Perform hybrid search over the indexed corpus."""

    request = HybridSearchRequest(
        query=q,
        osis=osis,
        filters=HybridSearchFilters(
            collection=collection,
            author=author,
            source_type=source_type,
            theological_tradition=theological_tradition,
            topic_domain=topic_domain,
        ),
        k=k,
    )
    results, reranker_header = retrieval_service.search(session, request)

    if reranker_header:
        response.headers["X-Reranker"] = reranker_header

    return HybridSearchResponse(query=q, osis=osis, results=results)
