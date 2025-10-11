"""Ingestion pipeline orchestration entry points."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.request import build_opener as _urllib_build_opener

from sqlalchemy.orm import Session

from ..core.settings import get_settings
from ..db.models import Document, TranscriptSegment
from ..telemetry import instrument_workflow, set_span_attribute
from .embeddings import get_embedding_service
from .exceptions import UnsupportedSourceError
from .metadata import load_frontmatter, merge_metadata, parse_text_file
from . import network as ingest_network
from .network import fetch_web_document
from .orchestrator import IngestOrchestrator, OrchestratorResult
from .persistence import refresh_creator_verse_rollups
from .stages import (
    DefaultErrorPolicy,
    EmbeddingServiceProtocol,
    Enricher,
    ErrorPolicy,
    IngestContext,
    Instrumentation,
    Parser,
    Persister,
    SourceFetcher,
)
from .stages.enrichers import DocumentEnricher
from .stages.fetchers import FileSourceFetcher, TranscriptSourceFetcher, UrlSourceFetcher
from .stages.parsers import FileParser, TranscriptParser, UrlParser
from .stages.persisters import TextDocumentPersister, TranscriptDocumentPersister


__all__ = [
    "PipelineDependencies",
    "_parse_text_file",
    "parse_text_file",
    "_refresh_creator_verse_rollups",
    "build_opener",
    "_fetch_web_document",
    "_WEB_FETCH_CHUNK_SIZE",
    "ensure_url_allowed",
    "run_pipeline_for_file",
    "run_pipeline_for_transcript",
    "run_pipeline_for_url",
]


_parse_text_file = parse_text_file


@dataclass(slots=True)
class PipelineDependencies:
    """Runtime dependencies for the ingestion orchestrator."""

    embedding_service: EmbeddingServiceProtocol | None = None
    error_policy: ErrorPolicy | None = None

    def build_context(self, *, span) -> IngestContext:
        settings = get_settings()
        embedding = self.embedding_service or get_embedding_service()
        policy = self.error_policy or DefaultErrorPolicy()
        instrumentation = Instrumentation(span=span, setter=set_span_attribute)
        return IngestContext(
            settings=settings,
            embedding_service=embedding,
            instrumentation=instrumentation,
            error_policy=policy,
        )


def _default_orchestrator(
    stages: Iterable[SourceFetcher | Parser | Enricher | Persister]
) -> IngestOrchestrator:
    return IngestOrchestrator(stages)


def _ensure_success(result: OrchestratorResult) -> Document:
    if result.status == "success" and result.document is not None:
        return result.document

    if result.failures:
        failure = result.failures[-1]
    elif result.stages:
        failure = result.stages[-1]
    else:  # pragma: no cover - defensive branch
        raise UnsupportedSourceError("Ingestion failed without stage execution")

    if failure.error:
        raise failure.error
    raise UnsupportedSourceError("Ingestion failed without error metadata")


def ensure_url_allowed(settings, url: str) -> None:
    """Validate URL targets using the current resolve-host strategy."""

    original_resolver = ingest_network.resolve_host_addresses
    ingest_network.resolve_host_addresses = _resolve_host_addresses
    try:
        ingest_network.ensure_url_allowed(settings, url)
    except UnsupportedSourceError:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname
        if host:
            normalised_host = ingest_network.normalise_host(host)
            allowed_hosts = {item.lower() for item in settings.ingest_url_allowed_hosts}
            if normalised_host in allowed_hosts:
                addresses = _resolve_host_addresses(normalised_host)
                ingest_network.ensure_resolved_addresses_allowed(settings, addresses)
                return
        raise
    finally:
        ingest_network.resolve_host_addresses = original_resolver


_resolve_host_addresses = ingest_network.resolve_host_addresses


build_opener = _urllib_build_opener
_WEB_FETCH_CHUNK_SIZE = 64 * 1024


def _fetch_web_document(settings, url: str):
    return fetch_web_document(settings, url, opener_factory=build_opener)


def _orchestrate(
    *,
    session: Session,
    dependencies: PipelineDependencies | None,
    stages: Iterable[SourceFetcher | Parser | Enricher | Persister],
    workflow: str,
    workflow_kwargs: dict[str, Any],
) -> Document:
    pipeline_dependencies = dependencies or PipelineDependencies()
    with instrument_workflow(workflow, **workflow_kwargs) as span:
        context = pipeline_dependencies.build_context(span=span)
        orchestrator = _default_orchestrator(stages)
        result = orchestrator.run(context=context)
        document = _ensure_success(result)
        return document


def _file_title_default(state: dict[str, Any]) -> str:
    path = state.get("path")
    if isinstance(path, Path):
        return path.stem
    return Path(str(path)).stem if path else "Document"


def _transcript_title_default(state: dict[str, Any]) -> str:
    path = state.get("transcript_path")
    if isinstance(path, Path):
        return path.stem
    return "Transcript"


def run_pipeline_for_file(
    session: Session,
    path: Path,
    frontmatter: dict[str, Any] | None = None,
    *,
    dependencies: PipelineDependencies | None = None,
) -> Document:
    """Execute the file ingestion pipeline synchronously."""

    frontmatter_payload = merge_metadata({}, load_frontmatter(frontmatter))
    stages = [
        FileSourceFetcher(path=path, frontmatter=frontmatter_payload),
        FileParser(),
        DocumentEnricher(default_title_factory=_file_title_default),
        TextDocumentPersister(session=session),
    ]
    return _orchestrate(
        session=session,
        dependencies=dependencies,
        stages=stages,
        workflow="ingest.file",
        workflow_kwargs={"source_path": str(path), "source_name": path.name},
    )


def _url_title_default(state: dict[str, Any]) -> str:
    if state.get("source_type") == "youtube":
        video_id = state.get("video_id")
        if video_id:
            return f"YouTube Video {video_id}"
    return state.get("url") or "Document"


def run_pipeline_for_url(
    session: Session,
    url: str,
    source_type: str | None = None,
    frontmatter: dict[str, Any] | None = None,
    *,
    dependencies: PipelineDependencies | None = None,
) -> Document:
    """Ingest supported URLs into the document store."""

    frontmatter_payload = merge_metadata({}, load_frontmatter(frontmatter))

    class _UrlDocumentPersister(Persister):
        name = "url_document_persister"

        def __init__(self, *, session: Session) -> None:
            self._text_persister = TextDocumentPersister(session=session)
            self._transcript_persister = TranscriptDocumentPersister(session=session)

        def persist(self, *, context, state: dict[str, Any]):  # type: ignore[override]
            if state.get("source_type") == "youtube":
                return self._transcript_persister.persist(context=context, state=state)
            return self._text_persister.persist(context=context, state=state)

    stages = [
        UrlSourceFetcher(
            url=url,
            source_type=source_type,
            frontmatter=frontmatter_payload,
            ensure_url_allowed_fn=ensure_url_allowed,
            fetch_document_fn=_fetch_web_document,
        ),
        UrlParser(),
        DocumentEnricher(default_title_factory=_url_title_default),
        _UrlDocumentPersister(session=session),
    ]

    return _orchestrate(
        session=session,
        dependencies=dependencies,
        stages=stages,
        workflow="ingest.url",
        workflow_kwargs={"source_url": url, "requested_source_type": source_type},
    )


def run_pipeline_for_transcript(
    session: Session,
    transcript_path: Path,
    *,
    frontmatter: dict[str, Any] | None = None,
    audio_path: Path | None = None,
    transcript_filename: str | None = None,
    audio_filename: str | None = None,
    dependencies: PipelineDependencies | None = None,
) -> Document:
    """Ingest a transcript file and optional audio into the document store."""

    frontmatter_payload = merge_metadata({}, load_frontmatter(frontmatter))
    stages = [
        TranscriptSourceFetcher(
            transcript_path=transcript_path,
            frontmatter=frontmatter_payload,
            audio_path=audio_path,
            transcript_filename=transcript_filename,
            audio_filename=audio_filename,
        ),
        TranscriptParser(),
        DocumentEnricher(default_title_factory=_transcript_title_default),
        TranscriptDocumentPersister(session=session),
    ]
    return _orchestrate(
        session=session,
        dependencies=dependencies,
        stages=stages,
        workflow="ingest.transcript",
        workflow_kwargs={
            "transcript_path": str(transcript_path),
            "audio_path": str(audio_path) if audio_path else None,
        },
    )


def _refresh_creator_verse_rollups(
    session: Session, segments: Iterable[TranscriptSegment]
) -> None:
    """Backwards-compatible wrapper for legacy imports."""

    context = PipelineDependencies().build_context(span=None)
    refresh_creator_verse_rollups(session, list(segments), context=context)
