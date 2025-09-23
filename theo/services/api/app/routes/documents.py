from fastapi import APIRouter

from ..models.documents import DocumentDetailResponse
from ..retriever.documents import get_document

router = APIRouter()


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def document_detail(document_id: str):
    """Fetch a document with its metadata and passages."""
    document = get_document(document_id)
    return document
