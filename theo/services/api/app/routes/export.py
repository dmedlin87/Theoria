"""Export endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..models.export import DocumentExportFilters, DocumentExportResponse, SearchExportResponse
from ..models.search import HybridSearchFilters, HybridSearchRequest
from ..retriever.export import export_documents, export_search_results

router = APIRouter()


@router.get("/search", response_model=SearchExportResponse)
def export_search(
    q: str | None = Query(default=None, description="Keyword query to run."),
    osis: str | None = Query(default=None, description="Optional OSIS reference to filter by."),
    collection: str | None = Query(default=None, description="Filter results to a collection."),
    author: str | None = Query(default=None, description="Filter by author."),
    source_type: str | None = Query(default=None, description="Restrict to a specific source type."),
    k: int = Query(default=100, ge=1, le=1000, description="Maximum number of results to export."),
    session: Session = Depends(get_session),
) -> SearchExportResponse:
    """Return up to *k* hybrid search results with document metadata."""

    request = HybridSearchRequest(
        query=q,
        osis=osis,
        k=k,
        filters=HybridSearchFilters(collection=collection, author=author, source_type=source_type),
    )
    return export_search_results(session, request)


@router.get("/documents", response_model=DocumentExportResponse)
def export_documents_endpoint(
    collection: str | None = Query(default=None, description="Collection to export."),
    author: str | None = Query(default=None, description="Filter documents by author."),
    source_type: str | None = Query(default=None, description="Restrict to a source type."),
    include_passages: bool = Query(default=True, description="Whether to include passages in the export."),
    limit: int | None = Query(default=None, ge=1, le=1000, description="Maximum number of documents to export."),
    session: Session = Depends(get_session),
) -> DocumentExportResponse:
    """Return documents and their passages for offline processing."""

    filters = DocumentExportFilters(collection=collection, author=author, source_type=source_type)
    return export_documents(session, filters, include_passages=include_passages, limit=limit)

