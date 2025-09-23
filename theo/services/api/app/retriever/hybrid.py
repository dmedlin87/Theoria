"""Hybrid search interface (vector + lexical)."""

from ..models.search import HybridSearchRequest, HybridSearchResult


def hybrid_search(request: HybridSearchRequest) -> list[HybridSearchResult]:
    """Placeholder hybrid search implementation.

    The MVP will replace this stub with a real pgvector + tsvector query. For now we
    return an empty list so the API contract is respected while the database layer is
    implemented.
    """

    return []
