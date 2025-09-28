"""Ingestion endpoints."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from uuid import uuid4
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.settings import get_settings
from ..ingest.pipeline import (
    UnsupportedSourceError,
    run_pipeline_for_file,
    run_pipeline_for_transcript,
    run_pipeline_for_url,
)
from ..models.documents import DocumentIngestResponse, UrlIngestRequest

router = APIRouter()


_UPLOAD_CHUNK_SIZE = 1024 * 1024


def _parse_frontmatter(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid frontmatter JSON"
        ) from exc


def _unique_safe_path(tmp_dir: Path, filename: str | None, default: str) -> Path:
    """Return a unique, sanitized path anchored within ``tmp_dir``."""

    safe_name = Path(filename or "").name
    if not safe_name:
        safe_name = Path(default).name or "upload.bin"
    unique_name = f"{uuid4().hex}-{safe_name}"
    return tmp_dir / unique_name


async def _iter_upload_chunks(
    upload: UploadFile, chunk_size: int = _UPLOAD_CHUNK_SIZE
) -> AsyncIterator[bytes]:
    while True:
        chunk = await upload.read(chunk_size)
        if not chunk:
            break
        yield chunk


async def _stream_upload_to_path(
    upload: UploadFile,
    destination: Path,
    *,
    max_bytes: int | None,
    chunk_size: int = _UPLOAD_CHUNK_SIZE,
) -> int:
    written = 0
    with destination.open("wb") as handle:
        async for chunk in _iter_upload_chunks(upload, chunk_size=chunk_size):
            written += len(chunk)
            if max_bytes is not None and written > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Upload exceeds maximum allowed size",
                )
            handle.write(chunk)
    return written


@router.post("/file", response_model=DocumentIngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    frontmatter: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> DocumentIngestResponse:
    """Accept a file upload and synchronously process it into passages."""

    tmp_dir = Path(tempfile.mkdtemp(prefix="theo-ingest-"))
    tmp_path = _unique_safe_path(tmp_dir, file.filename, "upload.bin")
    settings = get_settings()

    try:
        await _stream_upload_to_path(
            file,
            tmp_path,
            max_bytes=getattr(settings, "ingest_upload_max_bytes", None),
        )
        parsed_frontmatter = _parse_frontmatter(frontmatter)
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
    transcript_path = _unique_safe_path(
        tmp_dir, transcript.filename, "transcript.vtt"
    )
    audio_path: Path | None = None

    settings = get_settings()
    limit = getattr(settings, "ingest_upload_max_bytes", None)

    try:
        await _stream_upload_to_path(transcript, transcript_path, max_bytes=limit)

        if audio is not None:
            audio_path = _unique_safe_path(tmp_dir, audio.filename, "audio.bin")
            await _stream_upload_to_path(audio, audio_path, max_bytes=limit)

        parsed_frontmatter = _parse_frontmatter(frontmatter)

        document = run_pipeline_for_transcript(
            session,
            transcript_path,
            frontmatter=parsed_frontmatter,
            audio_path=audio_path,
            transcript_filename=Path(transcript.filename or "transcript.vtt").name,
            audio_filename=(Path(audio.filename).name if audio and audio.filename else None),
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
