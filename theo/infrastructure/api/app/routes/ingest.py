"""Ingestion endpoints."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator, Iterator
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session
from theo.application.facades.settings import get_settings

from ..discoveries.tasks import schedule_discovery_refresh
from ..errors import IngestionError, Severity
from ..ingest.exceptions import UnsupportedSourceError
from ..ingest.pipeline import (
    run_pipeline_for_file as _run_pipeline_for_file,
    run_pipeline_for_transcript as _run_pipeline_for_transcript,
    run_pipeline_for_url as _run_pipeline_for_url,
)
from ..models.documents import (
    DocumentIngestResponse,
    SimpleIngestRequest,
    UrlIngestRequest,
)
from ..persistence_models import Document
from theo.application.facades.resilience import (
    ResilienceError,
    ResilienceSettings,
    resilient_async_operation,
)
from theo.application.security import Principal

from ..adapters.security import require_principal
from ..infra.ingestion_service import IngestionService, get_ingestion_service
from ..utils.imports import LazyImportModule

cli_ingest = LazyImportModule("theo.infrastructure.cli.ingest_folder")

# Backwards-compatible shims that mirror the previous direct pipeline imports.
# Older tests and extensions reach into ``routes.ingest`` and replace these
# attributes, so keep them stable and ensure the ingestion service picks up any
# monkeypatching.
run_pipeline_for_file = _run_pipeline_for_file
run_pipeline_for_transcript = _run_pipeline_for_transcript
run_pipeline_for_url = _run_pipeline_for_url

# Starlette's payload-too-large HTTP status constant.
try:  # pragma: no branch - prefer new constant when available
    _PAYLOAD_TOO_LARGE_STATUS = status.HTTP_413_CONTENT_TOO_LARGE
except AttributeError:  # pragma: no cover - compatibility for older Starlette
    _PAYLOAD_TOO_LARGE_STATUS = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

_INGEST_ERROR_RESPONSES = {
    status.HTTP_400_BAD_REQUEST: {"description": "Invalid ingest request"},
    _PAYLOAD_TOO_LARGE_STATUS: {"description": "Upload too large"},
}


def _ingestion_service_with_overrides(
    ingestion_service: IngestionService = Depends(get_ingestion_service),
) -> IngestionService:
    """Ensure ingestion dependencies respect route-level monkeypatches."""

    if run_pipeline_for_file is not _run_pipeline_for_file:
        ingestion_service.run_file_pipeline = run_pipeline_for_file
    if run_pipeline_for_transcript is not _run_pipeline_for_transcript:
        ingestion_service.run_transcript_pipeline = run_pipeline_for_transcript
    if run_pipeline_for_url is not _run_pipeline_for_url:
        ingestion_service.run_url_pipeline = run_pipeline_for_url
    return ingestion_service


router = APIRouter()


_UPLOAD_CHUNK_SIZE = 1024 * 1024


def _principal_subject(principal: Principal | None) -> str | None:
    if not principal:
        return None
    subject = principal.get("subject")
    if isinstance(subject, str) and subject.strip():
        return subject.strip()
    return None


def _frontmatter_with_owner(
    frontmatter: dict[str, Any] | None, user_id: str | None
) -> dict[str, Any] | None:
    if not user_id:
        return frontmatter
    enriched = dict(frontmatter) if frontmatter else {}
    enriched.setdefault("collection", user_id)
    enriched.setdefault("owner_user_id", user_id)
    enriched.setdefault("uploaded_by", user_id)
    return enriched


def _parse_frontmatter(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise IngestionError(
            "Invalid frontmatter JSON",
            code="INGESTION_INVALID_FRONTMATTER",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Ensure frontmatter is valid JSON before submitting the request.",
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
    async def _write() -> int:
        written = 0
        with destination.open("wb") as handle:
            async for chunk in _iter_upload_chunks(upload, chunk_size=chunk_size):
                written += len(chunk)
                if max_bytes is not None and written > max_bytes:
                    raise IngestionError(
                        "Upload exceeds maximum allowed size",
                        code="INGESTION_UPLOAD_TOO_LARGE",
                        status_code=_PAYLOAD_TOO_LARGE_STATUS,
                        severity=Severity.USER,
                        hint="Reduce the file size or configure a larger quota before retrying.",
                    )
                try:
                    handle.write(chunk)
                except OSError as exc:
                    raise IngestionError(
                        "Failed to persist uploaded file",
                        code="INGESTION_UPLOAD_IO_ERROR",
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        severity=Severity.TRANSIENT,
                        hint="Retry the upload or check storage permissions.",
                    ) from exc
        return written

    try:
        result, _metadata = await resilient_async_operation(
            _write,
            key=f"ingest:upload:{destination.suffix or 'bin'}",
            classification="file",
            settings=ResilienceSettings(max_attempts=1),
        )
    except ResilienceError as exc:
        cause = exc.__cause__
        if isinstance(cause, IngestionError):
            raise cause
        raise IngestionError(
            "Upload failed due to storage error",
            code="INGESTION_UPLOAD_FAILURE",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            severity=Severity.TRANSIENT,
            hint="Retry the upload once the storage service is healthy.",
            data={"resilience": exc.metadata.to_dict()},
        ) from exc
    return result


def _encode_event(event: dict[str, Any]) -> bytes:
    payload = json.dumps(event, separators=(",", ":"))
    return f"{payload}\n".encode("utf-8")


@router.post(
    "/file",
    response_model=DocumentIngestResponse,
    responses=_INGEST_ERROR_RESPONSES,
)
async def ingest_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    frontmatter: str | None = Form(default=None),
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
    ingestion_service: IngestionService = Depends(
        _ingestion_service_with_overrides
    ),
) -> DocumentIngestResponse:
    """Accept a file upload and synchronously process it into passages."""

    tmp_dir = Path(tempfile.mkdtemp(prefix="theo-ingest-"))
    tmp_path = _unique_safe_path(tmp_dir, file.filename, "upload.bin")
    settings = get_settings()

    user_id = _principal_subject(principal)

    try:
        await _stream_upload_to_path(
            file,
            tmp_path,
            max_bytes=getattr(settings, "ingest_upload_max_bytes", None),
        )
        parsed_frontmatter = _parse_frontmatter(frontmatter)
        enriched_frontmatter = _frontmatter_with_owner(parsed_frontmatter, user_id)
        if ingestion_service.run_file_pipeline is _run_pipeline_for_file:
            ingestion_service.run_file_pipeline = run_pipeline_for_file
        document = ingestion_service.ingest_file(
            session,
            tmp_path,
            enriched_frontmatter,
        )
    except IngestionError:
        raise
    except ResilienceError as exc:
        raise IngestionError(
            "Ingestion pipeline failed while processing the file",
            code="INGESTION_PIPELINE_FAILURE",
            status_code=status.HTTP_502_BAD_GATEWAY,
            severity=Severity.TRANSIENT,
            hint="Retry the request once dependent services recover.",
            data={"resilience": exc.metadata.to_dict()},
        ) from exc
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
            tmp_dir.rmdir()
        except OSError:
            pass

    schedule_discovery_refresh(background_tasks, user_id)
    return DocumentIngestResponse(document_id=document.id, status="processed")


@router.post(
    "/url",
    response_model=DocumentIngestResponse,
    responses=_INGEST_ERROR_RESPONSES,
)
async def ingest_url(
    background_tasks: BackgroundTasks,
    payload: UrlIngestRequest,
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
    ingestion_service: IngestionService = Depends(
        _ingestion_service_with_overrides
    ),
) -> DocumentIngestResponse:
    user_id = _principal_subject(principal)
    frontmatter = _frontmatter_with_owner(payload.frontmatter, user_id)
    try:
        if ingestion_service.run_url_pipeline is _run_pipeline_for_url:
            ingestion_service.run_url_pipeline = run_pipeline_for_url
        document = ingestion_service.ingest_url(
            session,
            payload.url,
            source_type=payload.source_type,
            frontmatter=frontmatter,
        )
    except UnsupportedSourceError as exc:
        raise IngestionError(
            str(exc),
            code="INGESTION_UNSUPPORTED_SOURCE",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Review the URL and ensure it meets ingestion requirements.",
        ) from exc
    except ResilienceError as exc:
        raise IngestionError(
            "Failed to fetch remote content",
            code="INGESTION_NETWORK_FAILURE",
            status_code=status.HTTP_502_BAD_GATEWAY,
            severity=Severity.TRANSIENT,
            hint="Retry after the upstream provider recovers.",
            data={"resilience": exc.metadata.to_dict()},
        ) from exc

    schedule_discovery_refresh(background_tasks, user_id)
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
        raise IngestionError(
            str(exc),
            code="INGESTION_CONFIGURATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Review the provided ingest sources and configuration.",
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
    background_tasks: BackgroundTasks,
    transcript: UploadFile = File(...),
    audio: UploadFile | None = File(default=None),
    frontmatter: str | None = Form(default=None),
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
    ingestion_service: IngestionService = Depends(
        _ingestion_service_with_overrides
    ),
) -> DocumentIngestResponse:
    """Accept a transcript (and optional audio) and process it into passages."""

    tmp_dir = Path(tempfile.mkdtemp(prefix="theo-ingest-"))
    transcript_path = _unique_safe_path(
        tmp_dir, transcript.filename, "transcript.vtt"
    )
    audio_path: Path | None = None

    settings = get_settings()
    limit = getattr(settings, "ingest_upload_max_bytes", None)

    user_id = _principal_subject(principal)

    try:
        await _stream_upload_to_path(transcript, transcript_path, max_bytes=limit)

        if audio is not None:
            audio_path = _unique_safe_path(tmp_dir, audio.filename, "audio.bin")
            await _stream_upload_to_path(audio, audio_path, max_bytes=limit)

        parsed_frontmatter = _parse_frontmatter(frontmatter)
        enriched_frontmatter = _frontmatter_with_owner(parsed_frontmatter, user_id)
        if ingestion_service.run_transcript_pipeline is _run_pipeline_for_transcript:
            ingestion_service.run_transcript_pipeline = run_pipeline_for_transcript

        document = ingestion_service.ingest_transcript(
            session,
            transcript_path,
            frontmatter=enriched_frontmatter,
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
    except IngestionError:
        raise
    except ResilienceError as exc:
        raise IngestionError(
            "Transcript processing failed",
            code="INGESTION_TRANSCRIPT_FAILURE",
            status_code=status.HTTP_502_BAD_GATEWAY,
            severity=Severity.TRANSIENT,
            hint="Retry once the transcription pipeline is healthy.",
            data={"resilience": exc.metadata.to_dict()},
        ) from exc
    finally:
        try:
            if audio_path:
                audio_path.unlink(missing_ok=True)
            transcript_path.unlink(missing_ok=True)
            tmp_dir.rmdir()
        except OSError:
            pass

    schedule_discovery_refresh(background_tasks, user_id)
    return DocumentIngestResponse(document_id=document.id, status="processed")


@router.post(
    "/audio",
    response_model=DocumentIngestResponse,
    responses=_INGEST_ERROR_RESPONSES,
)
async def ingest_audio(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    source_type: str = Form(default="user_upload"),
    frontmatter: str | None = Form(default=None),
    notebooklm_metadata: str | None = Form(default=None),
    principal: Principal = Depends(require_principal),
    session: Session = Depends(get_session),
    ingestion_service: IngestionService = Depends(
        _ingestion_service_with_overrides
    ),
) -> DocumentIngestResponse:
    """Ingest an audio file (MP3, WAV) or video file (MP4) with transcription."""
    principal_subject = _principal_subject(principal)

    try:
        # Parse NotebookLM metadata if provided
        nb_metadata = {}
        if notebooklm_metadata:
            try:
                nb_metadata = json.loads(notebooklm_metadata)
            except json.JSONDecodeError:
                raise IngestionError(
                    "Invalid NotebookLM metadata JSON",
                    code="INGESTION_INVALID_NOTEBOOKLM_METADATA",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    severity=Severity.USER,
                    hint="Ensure NotebookLM metadata is valid JSON before submitting the request.",
                )

        # Merge with frontmatter
        parsed_frontmatter = _parse_frontmatter(frontmatter)
        enriched_frontmatter = _frontmatter_with_owner(
            parsed_frontmatter, principal_subject
        )
        if nb_metadata:
            enriched_frontmatter.setdefault("notebooklm", nb_metadata)
        enriched_frontmatter.setdefault("content_type", "audio")
        enriched_frontmatter.setdefault("source_type", source_type)

        # Create temp file
        tmp_dir = Path(tempfile.mkdtemp(prefix="theo-ingest-"))
        tmp_path = _unique_safe_path(tmp_dir, audio.filename, "audio.bin")
        settings = get_settings()
        limit = getattr(settings, "ingest_upload_max_bytes", None)
        document: Document | None = None
        try:
            await _stream_upload_to_path(
                audio,
                tmp_path,
                max_bytes=limit,
            )

            # Process via ingestion service
            document = ingestion_service.ingest_audio(
                session,
                tmp_path,
                source_type=source_type,
                frontmatter=enriched_frontmatter,
            )
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
            try:
                tmp_dir.rmdir()
            except OSError:
                pass

        schedule_discovery_refresh(background_tasks, principal_subject)
        return DocumentIngestResponse(document_id=document.id, status="processed")

    except IngestionError:
        raise
    except Exception as e:
        raise IngestionError(
            "Audio ingestion failed",
            code="INGESTION_AUDIO_FAILURE",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            severity=Severity.TRANSIENT,
            hint="Retry once the ingestion service is healthy.",
        ) from e
