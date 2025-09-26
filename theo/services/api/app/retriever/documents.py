"""Document retrieval helpers."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db.models import Document, DocumentAnnotation, Passage
from ..models.base import Passage as PassageSchema
from ..models.documents import (
    DocumentAnnotationCreate,
    DocumentAnnotationResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentPassagesResponse,
    DocumentSummary,
    DocumentUpdateRequest,
)


def _passage_to_schema(passage: Passage) -> PassageSchema:
    return PassageSchema(
        id=passage.id,
        document_id=passage.document_id,
        text=passage.text,
        osis_ref=passage.osis_ref,
        page_no=passage.page_no,
        t_start=passage.t_start,
        t_end=passage.t_end,
        score=None,
        meta=passage.meta,
    )


def _annotation_to_schema(annotation: DocumentAnnotation) -> DocumentAnnotationResponse:
    return DocumentAnnotationResponse(
        id=annotation.id,
        document_id=annotation.document_id,
        body=annotation.body,
        created_at=annotation.created_at,
        updated_at=annotation.updated_at,
    )


def list_documents(
    session: Session, *, limit: int = 20, offset: int = 0
) -> DocumentListResponse:
    """Return a paginated set of document summaries."""

    query = session.query(Document).order_by(Document.created_at.desc())
    total = session.query(func.count(Document.id)).scalar() or 0
    rows = query.offset(offset).limit(limit).all()

    items = [
        DocumentSummary(
            id=row.id,
            title=row.title,
            source_type=row.source_type,
            collection=row.collection,
            authors=row.authors,
            doi=row.doi,
            venue=row.venue,
            year=row.year,
            created_at=row.created_at,
            updated_at=row.updated_at,
            provenance_score=row.provenance_score,
        )
        for row in rows
    ]

    return DocumentListResponse(items=items, total=total, limit=limit, offset=offset)


def get_document(session: Session, document_id: str) -> DocumentDetailResponse:
    """Fetch a document and its passages from the database."""

    document = session.get(Document, document_id)
    if document is None:
        raise KeyError(f"Document {document_id} not found")

    passages = (
        session.query(Passage)
        .filter(Passage.document_id == document.id)
        .order_by(Passage.page_no.asc(), Passage.start_char.asc())
        .all()
    )
    annotations = (
        session.query(DocumentAnnotation)
        .filter(DocumentAnnotation.document_id == document.id)
        .order_by(DocumentAnnotation.created_at.asc())
        .all()
    )

    passage_schemas = [_passage_to_schema(passage) for passage in passages]

    return DocumentDetailResponse(
        id=document.id,
        title=document.title,
        source_type=document.source_type,
        collection=document.collection,
        authors=document.authors,
        doi=document.doi,
        venue=document.venue,
        year=document.year,
        created_at=document.created_at,
        updated_at=document.updated_at,
        source_url=document.source_url,
        channel=document.channel,
        video_id=document.video_id,
        duration_seconds=document.duration_seconds,
        storage_path=document.storage_path,
        abstract=document.abstract,
        topics=document.topics,
        enrichment_version=document.enrichment_version,
        provenance_score=document.provenance_score,
        metadata=document.bib_json,
        passages=passage_schemas,
        annotations=[_annotation_to_schema(annotation) for annotation in annotations],
    )


def get_document_passages(
    session: Session,
    document_id: str,
    *,
    limit: int = 20,
    offset: int = 0,
) -> DocumentPassagesResponse:
    """Return paginated passages for a document."""

    document = session.get(Document, document_id)
    if document is None:
        raise KeyError(f"Document {document_id} not found")

    passage_query = (
        session.query(Passage)
        .filter(Passage.document_id == document.id)
        .order_by(Passage.page_no.asc(), Passage.start_char.asc())
    )
    total = (
        session.query(func.count(Passage.id))
        .filter(Passage.document_id == document.id)
        .scalar()
        or 0
    )
    passages = passage_query.offset(offset).limit(limit).all()

    return DocumentPassagesResponse(
        document_id=document.id,
        passages=[_passage_to_schema(p) for p in passages],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_latest_digest_document(session: Session) -> DocumentDetailResponse:
    """Return the most recently generated topic digest document."""

    digest = (
        session.query(Document)
        .filter(Document.source_type == "digest")
        .order_by(Document.created_at.desc())
        .first()
    )
    if digest is None:
        raise KeyError("No topic digest document available")
    return get_document(session, digest.id)


def update_document(
    session: Session,
    document_id: str,
    payload: DocumentUpdateRequest,
) -> DocumentDetailResponse:
    document = session.get(Document, document_id)
    if document is None:
        raise KeyError(f"Document {document_id} not found")

    if payload.title is not None:
        document.title = payload.title or None
    if payload.collection is not None:
        document.collection = payload.collection or None
    if payload.authors is not None:
        document.authors = payload.authors or None
    if payload.source_type is not None:
        document.source_type = payload.source_type or None
    if payload.abstract is not None:
        document.abstract = payload.abstract or None
    if payload.metadata is not None:
        document.bib_json = payload.metadata

    session.add(document)
    session.commit()
    session.refresh(document)
    return get_document(session, document_id)


def list_annotations(
    session: Session, document_id: str
) -> list[DocumentAnnotationResponse]:
    document = session.get(Document, document_id)
    if document is None:
        raise KeyError(f"Document {document_id} not found")

    annotations = (
        session.query(DocumentAnnotation)
        .filter(DocumentAnnotation.document_id == document_id)
        .order_by(DocumentAnnotation.created_at.asc())
        .all()
    )
    return [_annotation_to_schema(annotation) for annotation in annotations]


def create_annotation(
    session: Session,
    document_id: str,
    payload: DocumentAnnotationCreate,
) -> DocumentAnnotationResponse:
    document = session.get(Document, document_id)
    if document is None:
        raise KeyError(f"Document {document_id} not found")

    annotation = DocumentAnnotation(document_id=document_id, body=payload.body)
    session.add(annotation)
    session.commit()
    session.refresh(annotation)
    return _annotation_to_schema(annotation)


def delete_annotation(session: Session, document_id: str, annotation_id: str) -> None:
    document = session.get(Document, document_id)
    if document is None:
        raise KeyError(f"Document {document_id} not found")

    annotation = session.get(DocumentAnnotation, annotation_id)
    if annotation is None or annotation.document_id != document_id:
        raise KeyError(
            f"Annotation {annotation_id} not found for document {document_id}"
        )

    session.delete(annotation)
    session.commit()
