from fastapi import APIRouter, BackgroundTasks, UploadFile

from ..models.documents import DocumentIngestResponse
from ..workers.tasks import queue_file_ingest, queue_url_ingest

router = APIRouter()


@router.post("/file", response_model=DocumentIngestResponse)
async def ingest_file(background: BackgroundTasks, file: UploadFile):
    """Accept a file upload and dispatch to the ingestion pipeline."""
    document = queue_file_ingest(background, file)
    return DocumentIngestResponse(document_id=document.document_id, status=document.status)


@router.post("/url", response_model=DocumentIngestResponse)
async def ingest_url(background: BackgroundTasks, url: str):
    """Accept a URL for ingestion via the worker pipeline."""
    document = queue_url_ingest(background, url)
    return DocumentIngestResponse(document_id=document.document_id, status=document.status)
