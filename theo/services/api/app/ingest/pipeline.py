"""Ingestion pipeline orchestration entry points."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.request import build_opener as _urllib_build_opener

from sqlalchemy.orm import Session

from theo.application.facades.graph import get_graph_projector
from theo.application.facades.settings import Settings, get_settings
from theo.application.graph import GraphProjector, NullGraphProjector
from theo.services.api.app.persistence_models import Document, TranscriptSegment

from ..resilience import ResilienceError, ResiliencePolicy, resilient_operation
from ..telemetry import instrument_workflow, set_span_attribute
from . import network as ingest_network
from .embeddings import get_embedding_service
from .exceptions import UnsupportedSourceError
from .metadata import Frontmatter, load_frontmatter, merge_metadata, parse_text_file
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
from .stages.fetchers import (
    FileSourceFetcher,
    OsisSourceFetcher,
    TranscriptSourceFetcher,
    UrlSourceFetcher,
)
from .stages.parsers import (
    FileParser,
    OsisCommentaryParser,
    TranscriptParser,
    UrlParser,
)
from .stages.persisters import (
    CommentarySeedPersister,
    TextDocumentPersister,
    TranscriptDocumentPersister,
)

logger = logging.getLogger(__name__)


_parse_text_file = parse_text_file

# Legacy alias retained for older tests/hooks that patch the private helper.
# Keep this close to the imports so reloads and import * behaviour keep the
# attribute available for existing integrations.  Some integration tests reach
# into the module to swap out the helper and expect it to exist even if the
# public ``parse_text_file`` symbol is renamed.  Using an explicit alias keeps
# the attribute stable across reloads and avoids AttributeErrors when tests
# access ``_parse_text_file`` before monkeypatching.


_resolve_host_addresses = ingest_network.resolve_host_addresses


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
    "import_osis_commentary",
]





@dataclass(slots=True)
class PipelineDependencies:
    """Runtime dependencies for the ingestion orchestrator."""

    settings: Settings | None = None
    embedding_service: EmbeddingServiceProtocol | None = None
    error_policy: ErrorPolicy | None = None
    graph_projector: GraphProjector | None = None

    def build_context(self, *, span) -> IngestContext:
        settings = self.settings or get_settings()
        embedding = self.embedding_service or get_embedding_service()
        policy = self.error_policy or DefaultErrorPolicy()
        projector = self.graph_projector
        if projector is None:
            try:
                projector = get_graph_projector()
            except Exception:  # pragma: no cover - defensive guard
                logger.exception("Failed to resolve graph projector")
                projector = NullGraphProjector()
        instrumentation = Instrumentation(span=span, setter=set_span_attribute)
        return IngestContext(
            settings=settings,
            embedding_service=embedding,
            instrumentation=instrumentation,
            error_policy=policy,
            graph_projector=projector,
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
                try:
                    addresses = _resolve_host_addresses(normalised_host)
                except UnsupportedSourceError:
                    # Allow-listed hosts intentionally bypass private-network checks.
                    # Resolution failures from private ranges are swallowed so ingest
                    # can proceed for explicitly trusted destinations.
                    return

                blocked_networks = ingest_network.cached_blocked_networks(
                    tuple(settings.ingest_url_blocked_ip_networks)
                )

                for resolved in addresses:
                    for network in blocked_networks:
                        if any(
                            getattr(network, attr, False)
                            for attr in ("is_private", "is_loopback", "is_link_local", "is_reserved")
                        ):
                            continue

                        if resolved in network:
                            raise UnsupportedSourceError(
                                "URL target is not allowed for ingestion"
                            )

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


def import_osis_commentary(
    session: Session,
    path: Path,
    frontmatter: dict[str, Any] | None = None,
    *,
    dependencies: PipelineDependencies | None = None,
):
    """Import commentary excerpts from an OSIS source file."""

    frontmatter_payload = merge_metadata({}, load_frontmatter(frontmatter))
    stages = [
        OsisSourceFetcher(path=path, frontmatter=frontmatter_payload),
        OsisCommentaryParser(),
        CommentarySeedPersister(session=session),
    ]

    pipeline_dependencies = dependencies or PipelineDependencies()
    with instrument_workflow(
        "ingest.osis", source_path=str(path), source_name=path.name
    ) as span:
        context = pipeline_dependencies.build_context(span=span)
        orchestrator = _default_orchestrator(stages)
        result = orchestrator.run(context=context)
        if result.status != "success":
            if result.failures:
                failure = result.failures[-1]
                if failure.error:
                    raise failure.error
            raise UnsupportedSourceError("OSIS import failed")
        import_result = result.state.get("commentary_result")
        if import_result is None:
            raise UnsupportedSourceError(
                "OSIS import completed without a commentary result"
            )
        return import_result


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
    settings, persistence_dependencies = _resolve_context(dependencies)
    with instrument_workflow(
        "ingest.file", source_path=str(path), source_name=path.name
    ) as span:
        try:
            raw_bytes, read_meta = resilient_operation(
                path.read_bytes,
                key=f"ingest:file:read:{path.suffix or 'bin'}",
                classification="file",
                policy=ResiliencePolicy(max_attempts=2),
            )
        except ResilienceError as exc:
            set_span_attribute(span, "resilience.file_read.category", exc.metadata.category)
            set_span_attribute(span, "resilience.file_read.attempts", exc.metadata.attempts)
            raise
        else:
            set_span_attribute(span, "resilience.file_read.attempts", read_meta.attempts)
            set_span_attribute(span, "resilience.file_read.duration", read_meta.duration)
        merged_frontmatter = merge_metadata(
            {}, load_frontmatter(frontmatter)
        )
        source_type = detect_source_type(path, merged_frontmatter)
        set_span_attribute(span, "ingest.source_type", source_type)

        parser_result, merged_frontmatter, text_content = _prepare_parser_result(
            source_type,
            path,
            frontmatter=merged_frontmatter,
            settings=settings,
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

        def persist(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
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
    settings, persistence_dependencies = _resolve_context(dependencies)
    with instrument_workflow(
        "ingest.url", source_url=url, requested_source_type=source_type
    ) as span:
        resolved_source_type = source_type or (
            "youtube" if is_youtube_url(url) else "web_page"
        )
        set_span_attribute(span, "ingest.source_type", resolved_source_type)

        ensure_url_allowed(settings, url)

        if resolved_source_type == "youtube":
            video_id = extract_youtube_video_id(url)
            metadata = load_youtube_metadata(settings, video_id)
            merged_frontmatter = merge_metadata(
                metadata, load_frontmatter(frontmatter)
            )

            segments, transcript_path = load_youtube_transcript(settings, video_id)
            parser_result = prepare_transcript_chunks(segments, settings=settings)
            sha256 = _hash_parser_result(parser_result)

            cache_status = "hit" if transcript_path else "miss"
            if transcript_path:
                set_span_attribute(span, "ingest.transcript_fixture", transcript_path.name)

            document = _ingest_transcript_document(
                session,
                span,
                dependencies=persistence_dependencies,
                parser_result=parser_result,
                frontmatter=merged_frontmatter,
                settings=settings,
                sha256=sha256,
                source_type="youtube",
                title=merged_frontmatter.get("title")
                or metadata.get("title")
                or f"YouTube Video {video_id}",
                cache_status=cache_status,
                source_url=merged_frontmatter.get("source_url") or url,
                channel=merged_frontmatter.get("channel") or metadata.get("channel"),
                video_id=video_id,
                duration_seconds=merged_frontmatter.get("duration_seconds")
                or metadata.get("duration_seconds"),
                transcript_path=transcript_path,
                transcript_filename=(transcript_path.name if transcript_path else None),
            )
            return document

        else:
            if resolved_source_type not in {"web_page", "html", "website"}:
                raise UnsupportedSourceError(
                    (
                        "Unsupported source type for URL ingestion: "
                        f"{resolved_source_type}. Supported types are: "
                        "youtube, web_page, html, website"
                    )
                )

            try:
                (html, metadata), fetch_meta = _fetch_web_document(settings, url)
            except ResilienceError as exc:
                set_span_attribute(span, "resilience.network.category", exc.metadata.category)
                set_span_attribute(span, "resilience.network.attempts", exc.metadata.attempts)
                raise
            else:
                set_span_attribute(span, "resilience.network.attempts", fetch_meta.attempts)
                set_span_attribute(span, "resilience.network.duration", fetch_meta.duration)
            text_content = html_to_text(html)
            if not text_content:
                raise UnsupportedSourceError(
                    "Fetched HTML did not contain extractable text"
                )

            merged_frontmatter = merge_metadata(metadata, load_frontmatter(frontmatter))
            parser_result = prepare_text_chunks(text_content, settings=settings)
            sha256 = _hash_parser_result(parser_result)

            document = _ingest_text_document(
                session,
                span,
                dependencies=persistence_dependencies,
                parser_result=parser_result,
                frontmatter=merged_frontmatter,
                settings=settings,
                sha256=sha256,
                source_type="web_page",
                title=merged_frontmatter.get("title") or metadata.get("title") or url,
                cache_status="n/a",
                source_url=merged_frontmatter.get("source_url")
                or metadata.get("canonical_url")
                or url,
                text_content=parser_result.text,
                raw_content=html,
                raw_filename="source.html",
            )

            return document


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
