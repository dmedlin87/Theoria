from fastapi import APIRouter, Query

from ..models.search import HybridSearchFilters, HybridSearchRequest, HybridSearchResponse
from ..retriever.hybrid import hybrid_search

router = APIRouter()


@router.get("/", response_model=HybridSearchResponse)
async def search(
    q: str | None = Query(default=None, description="Keyword query"),
    osis: str | None = Query(default=None, description="Normalized OSIS reference"),
):
    """Perform hybrid search over the indexed corpus."""
    request = HybridSearchRequest(query=q, osis=osis, filters=HybridSearchFilters())
    results = hybrid_search(request)
    return HybridSearchResponse(results=results)
