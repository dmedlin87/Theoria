"""Ingestion endpoints."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from uuid import uuid4
from typing import Any, AsyncIterator, Iterator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.database import get_session
from ..core.settings import get_settings
from ..ingest.exceptions import UnsupportedSourceError
from ..models.documents import (
    DocumentIngestResponse,
    SimpleIngestRequest,
    UrlIngestRequest,
)
from ..services.ingestion_service import IngestionService, get_ingestion_service

_INGEST_ERROR_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {"description": "Invalid ingest request"},
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {"description": "Upload too large"},
}


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


def _normalise_upload_name(filename: str | None, *, default: str) -> str:
    """Return a sanitised base filename for temporary upload storage."""

    candidate = (filename or "").strip()
    if candidate:
        # Some clients (notably Windows browsers) include backslashes in the
        # filename. Treat any slash variant as a directory separator so we do
        # not persist user supplied paths.
        candidate = candidate.replace("\\", "/")
        candidate = Path(candidate).name

    if not candidate:
        candidate = Path(default).name

    if not candidate:
        return "upload.bin"

    if candidate in {".", ".."}:
        return "upload.bin"

    return candidate


def _unique_safe_path(tmp_dir: Path, filename: str | None, default: str) -> Path:
    """Return a unique, sanitized path anchored within ``tmp_dir``."""

    safe_name = _normalise_upload_name(filename, default=default)
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
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Upload exceeds maximum allowed size",
                )
            handle.write(chunk)
    return written


def _encode_event(event: dict[str, Any]) -> bytes:
    payload = json.dumps(event, separators=(",", ":"))
    return f"{payload}\n".encode("utf-8")


@router.post(
    "/file",
    response_model=DocumentIngestResponse,
    responses=_INGEST_ERROR_RESPONSES,
)
async def ingest_file(
    file: UploadFile = File(...),
    frontmatter: str | None = Form(default=None),
    session: Session = Depends(get_session),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
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
        document = ingestion_service.ingest_file(
            session, tmp_path, parsed_frontmatter
        )
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


@router.post(
    "/url",
    response_model=DocumentIngestResponse,
    responses=_INGEST_ERROR_RESPONSES,
)
async def ingest_url(
    payload: UrlIngestRequest,
    session: Session = Depends(get_session),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> DocumentIngestResponse:
    try:
        document = ingestion_service.ingest_url(
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


@router.post(
    "/simple",
    responses=_INGEST_ERROR_RESPONSES,
)
async def simple_ingest(
    payload: SimpleIngestRequest,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> StreamingResponse:
    try:
        events = ingestion_service.stream_simple_ingest(payload)
        try:
            first_event = next(events)
        except StopIteration:
            first_event = None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    def _event_stream() -> Iterator[bytes]:
        if first_event is not None:
            yield _encode_event(first_event)
        for event in events:
            yield _encode_event(event)

    return StreamingResponse(
        _event_stream(), media_type="application/x-ndjson"
    )


@router.post(
    "/transcript",
    response_model=DocumentIngestResponse,
    responses=_INGEST_ERROR_RESPONSES,
)
async def ingest_transcript(
    transcript: UploadFile = File(...),
    audio: UploadFile | None = File(default=None),
    frontmatter: str | None = Form(default=None),
    session: Session = Depends(get_session),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
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

        document = ingestion_service.ingest_transcript(
            session,
            transcript_path,
            frontmatter=parsed_frontmatter,
            audio_path=audio_path,
            transcript_filename=_normalise_upload_name(
                transcript.filename, default="transcript.vtt"
            ),
            audio_filename=(
                _normalise_upload_name(audio.filename, default="audio.bin")
                if audio and audio.filename
                else None
            ),
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

