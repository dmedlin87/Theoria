"""Document retrieval helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import Document, Passage
from ..models.base import Passage as PassageSchema
from ..models.documents import DocumentDetailResponse


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

    passage_schemas = [
        PassageSchema(
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
        for passage in passages
    ]

    return DocumentDetailResponse(
        id=document.id,
        title=document.title,
        source_type=document.source_type,
        collection=document.collection,
        authors=document.authors,
        created_at=document.created_at,
        updated_at=document.updated_at,
        source_url=document.source_url,
        channel=document.channel,
        video_id=document.video_id,
        duration_seconds=document.duration_seconds,
        storage_path=document.storage_path,
        metadata=document.bib_json,
        passages=passage_schemas,
    )
