"""Background job management endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..db.models import Document
from ..workers.tasks import process_file

router = APIRouter()


def _resolve_source_file(storage_path: str | None) -> Path:
    if not storage_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document does not have stored source content",
        )

    storage_dir = Path(storage_path)
    if not storage_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stored source content is unavailable",
        )

    for candidate in sorted(storage_dir.iterdir()):
        if candidate.is_file() and candidate.name != "normalized.json":
            return candidate

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Stored source content is unavailable",
    )


@router.post("/reparse/{document_id}", status_code=status.HTTP_202_ACCEPTED)
def enqueue_reparse_job(
    document_id: str,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Queue a background reparse job for an existing document."""

    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    source_file = _resolve_source_file(document.storage_path)

    process_file.delay(document.id, str(source_file), None)

    return {"document_id": document.id, "status": "queued"}
