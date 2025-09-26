"""Ingestion endpoints."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..ingest.pipeline import (
    UnsupportedSourceError,
    run_pipeline_for_file,
    run_pipeline_for_transcript,
    run_pipeline_for_url,
)
from ..models.documents import DocumentIngestResponse, UrlIngestRequest

router = APIRouter()


def _parse_frontmatter(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid frontmatter JSON"
        ) from exc


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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return DocumentIngestResponse(document_id=document.id, status="processed")


@router.post("/transcript", response_model=DocumentIngestResponse)
async def ingest_transcript(
    transcript: UploadFile = File(...),
    audio: UploadFile | None = File(default=None),
    frontmatter: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> DocumentIngestResponse:
    """Accept a transcript (and optional audio) and process it into passages."""

    tmp_dir = Path(tempfile.mkdtemp(prefix="theo-ingest-"))
    transcript_name = transcript.filename or "transcript.vtt"
    transcript_path = tmp_dir / transcript_name
    audio_path: Path | None = None

    try:
        transcript_bytes = await transcript.read()
        with transcript_path.open("wb") as destination:
            destination.write(transcript_bytes)

        if audio is not None:
            audio_name = audio.filename or "audio.bin"
            audio_path = tmp_dir / audio_name
            audio_bytes = await audio.read()
            with audio_path.open("wb") as destination:
                destination.write(audio_bytes)

        parsed_frontmatter = _parse_frontmatter(frontmatter)

        document = run_pipeline_for_transcript(
            session,
            transcript_path,
            frontmatter=parsed_frontmatter,
            audio_path=audio_path,
        )
    except UnsupportedSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    finally:
        try:
            if audio_path:
                audio_path.unlink(missing_ok=True)
            transcript_path.unlink(missing_ok=True)
            tmp_dir.rmdir()
        except OSError:
            pass

    return DocumentIngestResponse(document_id=document.id, status="processed")
