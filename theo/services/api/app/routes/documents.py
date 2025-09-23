"""Document endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..models.documents import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentPassagesResponse,
)
from ..retriever.documents import get_document, get_document_passages, list_documents

router = APIRouter()


@router.get("/", response_model=DocumentListResponse)
def document_list(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> DocumentListResponse:
    """Return paginated documents."""

    return list_documents(session, limit=limit, offset=offset)


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def document_detail(document_id: str, session: Session = Depends(get_session)) -> DocumentDetailResponse:
    """Fetch a document with its metadata and passages."""

    try:
        return get_document(session, document_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{document_id}/passages", response_model=DocumentPassagesResponse)
def document_passages(
    document_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> DocumentPassagesResponse:
    """Return paginated passages for a given document."""

    try:
        return get_document_passages(session, document_id, limit=limit, offset=offset)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
