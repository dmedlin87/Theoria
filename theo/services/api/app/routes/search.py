"""Search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..models.search import HybridSearchFilters, HybridSearchRequest, HybridSearchResponse
from ..retriever.hybrid import hybrid_search

router = APIRouter()


@router.get("/", response_model=HybridSearchResponse)
def search(
    q: str | None = Query(default=None, description="Keyword query"),
    osis: str | None = Query(default=None, description="Normalized OSIS reference"),
    collection: str | None = Query(default=None, description="Restrict to a collection"),
    author: str | None = Query(default=None, description="Filter by author"),
    source_type: str | None = Query(default=None, description="Restrict to a source type"),
    k: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> HybridSearchResponse:
    """Perform hybrid search over the indexed corpus."""

    request = HybridSearchRequest(
        query=q,
        osis=osis,
        filters=HybridSearchFilters(collection=collection, author=author, source_type=source_type),
        k=k,
    )
    results = hybrid_search(session, request)
    return HybridSearchResponse(query=q, osis=osis, results=results)
