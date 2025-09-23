"""Document endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..models.documents import DocumentDetailResponse
from ..retriever.documents import get_document

router = APIRouter()


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def document_detail(document_id: str, session: Session = Depends(get_session)) -> DocumentDetailResponse:
    """Fetch a document with its metadata and passages."""

    try:
        return get_document(session, document_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
