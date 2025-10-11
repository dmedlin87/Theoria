"""Document endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..models.documents import (
    DocumentAnnotationCreate,
    DocumentAnnotationResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentPassagesResponse,
    DocumentUpdateRequest,
)
from ..errors import RetrievalError, Severity
from ..retriever.documents import (
    create_annotation,
    delete_annotation,
    get_document,
    get_document_passages,
    get_latest_digest_document,
    list_annotations,
    list_documents,
    update_document,
)

_DOCUMENT_NOT_FOUND_RESPONSE = {
    status.HTTP_404_NOT_FOUND: {"description": "Document not found"}
}


router = APIRouter()


@router.get("/", response_model=DocumentListResponse)
def document_list(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> DocumentListResponse:
    """Return paginated documents."""

    return list_documents(session, limit=limit, offset=offset)


@router.get(
    "/digest",
    response_model=DocumentDetailResponse,
    responses=_DOCUMENT_NOT_FOUND_RESPONSE,
)
def latest_digest_document(
    session: Session = Depends(get_session),
) -> DocumentDetailResponse:
    """Return the most recently generated topic digest document."""

    try:
        return get_latest_digest_document(session)
    except KeyError as exc:
        raise RetrievalError(
            str(exc),
            code="RETRIEVAL_DOCUMENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Verify the document exists before requesting the digest.",
        ) from exc


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    responses=_DOCUMENT_NOT_FOUND_RESPONSE,
)
def document_detail(
    document_id: str, session: Session = Depends(get_session)
) -> DocumentDetailResponse:
    """Fetch a document with its metadata and passages."""

    try:
        return get_document(session, document_id)
    except KeyError as exc:
        raise RetrievalError(
            str(exc),
            code="RETRIEVAL_DOCUMENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Confirm the document identifier is correct.",
        ) from exc


@router.get(
    "/{document_id}/passages",
    response_model=DocumentPassagesResponse,
    responses=_DOCUMENT_NOT_FOUND_RESPONSE,
)
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
        raise RetrievalError(
            str(exc),
            code="RETRIEVAL_DOCUMENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Confirm the document identifier is correct.",
        ) from exc


@router.patch(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    responses=_DOCUMENT_NOT_FOUND_RESPONSE,
)
def update_document_metadata(
    document_id: str,
    payload: DocumentUpdateRequest,
    session: Session = Depends(get_session),
) -> DocumentDetailResponse:
    """Update editable document metadata fields."""

    try:
        return update_document(session, document_id, payload)
    except KeyError as exc:
        raise RetrievalError(
            str(exc),
            code="RETRIEVAL_DOCUMENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Confirm the document identifier is correct.",
        ) from exc


@router.get(
    "/{document_id}/annotations",
    response_model=list[DocumentAnnotationResponse],
    responses=_DOCUMENT_NOT_FOUND_RESPONSE,
)
def document_annotations(
    document_id: str,
    session: Session = Depends(get_session),
) -> list[DocumentAnnotationResponse]:
    """Return annotations attached to the document."""

    try:
        return list_annotations(session, document_id)
    except KeyError as exc:
        raise RetrievalError(
            str(exc),
            code="RETRIEVAL_DOCUMENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Confirm the document identifier is correct.",
        ) from exc


@router.post(
    "/{document_id}/annotations",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentAnnotationResponse,
    responses=_DOCUMENT_NOT_FOUND_RESPONSE,
)
def create_document_annotation(
    document_id: str,
    payload: DocumentAnnotationCreate,
    session: Session = Depends(get_session),
) -> DocumentAnnotationResponse:
    """Create a new annotation for a document."""

    try:
        return create_annotation(session, document_id, payload)
    except KeyError as exc:
        raise RetrievalError(
            str(exc),
            code="RETRIEVAL_DOCUMENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Confirm the document identifier is correct.",
        ) from exc
    except ValueError as exc:
        raise RetrievalError(
            str(exc),
            code="RETRIEVAL_INVALID_ANNOTATION",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            severity=Severity.USER,
            hint="Adjust the annotation payload to satisfy validation rules.",
        ) from exc


@router.delete(
    "/{document_id}/annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_DOCUMENT_NOT_FOUND_RESPONSE,
)
def delete_document_annotation(
    document_id: str,
    annotation_id: str,
    session: Session = Depends(get_session),
) -> Response:
    """Delete a document annotation."""

    try:
        delete_annotation(session, document_id, annotation_id)
    except KeyError as exc:
        raise RetrievalError(
            str(exc),
            code="RETRIEVAL_DOCUMENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            severity=Severity.USER,
            hint="Confirm the document and annotation identifiers are correct.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
