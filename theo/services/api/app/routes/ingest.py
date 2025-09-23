"""Ingestion endpoints."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..models.documents import DocumentIngestResponse, UrlIngestRequest
from ..ingest.pipeline import UnsupportedSourceError, run_pipeline_for_file, run_pipeline_for_url

router = APIRouter()


def _parse_frontmatter(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid frontmatter JSON") from exc


@router.post("/file", response_model=DocumentIngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    frontmatter: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> DocumentIngestResponse:
    """Accept a file upload and synchronously process it into passages."""

    tmp_dir = Path(tempfile.mkdtemp(prefix="theo-ingest-"))
    tmp_path = tmp_dir / file.filename
    with tmp_path.open("wb") as destination:
        content = await file.read()
        destination.write(content)

    parsed_frontmatter = _parse_frontmatter(frontmatter)

    try:
        document = run_pipeline_for_file(session, tmp_path, parsed_frontmatter)
    except UnsupportedSourceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
            tmp_dir.rmdir()
        except OSError:
            pass

    return DocumentIngestResponse(document_id=document.id, status="processed")


@router.post("/url", response_model=DocumentIngestResponse)
async def ingest_url(
    payload: UrlIngestRequest,
    session: Session = Depends(get_session),
) -> DocumentIngestResponse:
    try:
        document = run_pipeline_for_url(
            session,
            payload.url,
            source_type=payload.source_type,
            frontmatter=payload.frontmatter,
        )
    except UnsupportedSourceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return DocumentIngestResponse(document_id=document.id, status="processed")
