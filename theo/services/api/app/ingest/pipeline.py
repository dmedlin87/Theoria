"""Ingestion pipeline orchestration entry points."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
from urllib.request import build_opener as _urllib_build_opener

from sqlalchemy.orm import Session

from ..core.settings import get_settings
from ..telemetry import instrument_workflow, set_span_attribute
from ..db.models import Document, TranscriptSegment
from .embeddings import get_embedding_service
from .exceptions import UnsupportedSourceError
from .metadata import (
    detect_source_type,
    html_to_text,
    load_frontmatter,
    merge_metadata,
    parse_text_file,
    prepare_pdf_chunks,
    prepare_text_chunks,
    prepare_transcript_chunks,
)
from . import network as ingest_network
from .network import (
    extract_youtube_video_id,
    fetch_web_document,
    is_youtube_url,
    load_youtube_metadata,
    load_youtube_transcript,
)
from .parsers import (
    ParserResult,
    load_transcript,
    parse_audio_document,
    parse_docx_document,
    parse_html_document,
)
from .persistence import (
    EmbeddingServiceProtocol,
    PersistenceDependencies,
    persist_text_document,
    persist_transcript_document,
    refresh_creator_verse_rollups,
)
from ..resilience import ResilienceError, ResiliencePolicy, resilient_operation


_resolve_host_addresses = ingest_network.resolve_host_addresses

# Legacy alias retained for older tests/hooks that patch the private helper.
# Keep this close to the imports so reloads and import * behaviour keep the
# attribute available for existing integrations.
_parse_text_file = parse_text_file


__all__ = [
    "PipelineDependencies",
    "_parse_text_file",
    "parse_text_file",
    "_refresh_creator_verse_rollups",
    "build_opener",
    "ensure_url_allowed",
    "run_pipeline_for_file",
    "run_pipeline_for_transcript",
    "run_pipeline_for_url",
]


def ensure_url_allowed(settings, url: str) -> None:
    """Validate URL targets using the current resolve-host strategy."""

    original_resolver = ingest_network.resolve_host_addresses
    ingest_network.resolve_host_addresses = _resolve_host_addresses
    try:
        ingest_network.ensure_url_allowed(settings, url)
    except UnsupportedSourceError:
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





@dataclass
class PipelineDependencies:
    """Runtime dependencies for the ingestion orchestrator."""

    embedding_service: EmbeddingServiceProtocol | None = None

    def for_persistence(self) -> PersistenceDependencies:
        service = self.embedding_service or get_embedding_service()
        return PersistenceDependencies(embedding_service=service)


def _resolve_context(
    dependencies: PipelineDependencies | None,
):
    """Resolve shared runtime state for orchestration entry points."""

    pipeline_dependencies = dependencies or PipelineDependencies()
    persistence_dependencies = pipeline_dependencies.for_persistence()
    settings = get_settings()
    return settings, persistence_dependencies


def _hash_parser_result(parser_result: ParserResult) -> str:
    payload = "\n".join(chunk.text for chunk in parser_result.chunks).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _persist_parser_result(
    persist_fn,
    *,
    session: Session,
    parser_result: ParserResult,
    persistence_dependencies: PersistenceDependencies,
    settings,
    span,
    frontmatter: dict[str, Any],
    cache_status: str | None = "n/a",
    **persist_kwargs,
):
    """Persist parsed content while recording common telemetry."""

    chunk_count = len(parser_result.chunks)
    set_span_attribute(span, "ingest.chunk_count", chunk_count)
    set_span_attribute(span, "ingest.batch_size", min(chunk_count, 32))
    if cache_status is not None:
        set_span_attribute(span, "ingest.cache_status", cache_status)

    document = persist_fn(
        session,
        dependencies=persistence_dependencies,
        chunks=parser_result.chunks,
        parser=parser_result.parser,
        parser_version=parser_result.parser_version,
        frontmatter=frontmatter,
        settings=settings,
        **persist_kwargs,
    )
    set_span_attribute(span, "ingest.document_id", document.id)
    return document


def _resolve_dependencies(
    dependencies: PipelineDependencies | None,
) -> PersistenceDependencies:
    """Normalise optional dependency overrides for persistence helpers."""

    if dependencies is None:
        dependencies = PipelineDependencies()
    return dependencies.for_persistence()
def _set_chunk_span_metrics(span, parser_result: ParserResult) -> None:
    chunk_count = len(parser_result.chunks)
    set_span_attribute(span, "ingest.chunk_count", chunk_count)
    set_span_attribute(span, "ingest.batch_size", min(chunk_count, 32))


def _ingest_transcript_document(
    session: Session,
    span,
    *,
    dependencies: PersistenceDependencies,
    parser_result: ParserResult,
    frontmatter: dict[str, Any],
    settings,
    sha256: str,
    source_type: str,
    title: str,
    cache_status: str,
    **persist_kwargs: Any,
) -> Document:
    """Persist transcript documents with consistent instrumentation."""

    return _persist_parser_result(
        persist_transcript_document,
        session=session,
        parser_result=parser_result,
        persistence_dependencies=dependencies,
        settings=settings,
        span=span,
        frontmatter=frontmatter,
        cache_status=cache_status,
        sha256=sha256,
        source_type=source_type,
        title=title,
        **persist_kwargs,
    )


def _ingest_text_document(
    session: Session,
    span,
    *,
    dependencies: PersistenceDependencies,
    parser_result: ParserResult,
    frontmatter: dict[str, Any],
    settings,
    sha256: str,
    source_type: str,
    title: str,
    cache_status: str,
    **persist_kwargs: Any,
) -> Document:
    """Persist text documents with consistent instrumentation."""

    return _persist_parser_result(
        persist_text_document,
        session=session,
        parser_result=parser_result,
        persistence_dependencies=dependencies,
        settings=settings,
        span=span,
        frontmatter=frontmatter,
        cache_status=cache_status,
        sha256=sha256,
        source_type=source_type,
        title=title,
        **persist_kwargs,
    )


def _prepare_parser_result(
    source_type: str,
    path: Path,
    *,
    frontmatter: dict[str, Any],
    settings,
) -> tuple[ParserResult, dict[str, Any], str]:
    parser_result: ParserResult | None = None
    text_content = ""
    merged_frontmatter = dict(frontmatter)

    if source_type in {"markdown", "txt", "file"}:
        text_content, parsed_frontmatter = parse_text_file(path)
        merged_frontmatter = merge_metadata(parsed_frontmatter, merged_frontmatter)
        parser_result = prepare_text_chunks(text_content, settings=settings)
    elif source_type == "docx":
        parser_result = parse_docx_document(path, max_tokens=settings.max_chunk_tokens)
        merged_frontmatter = merge_metadata(parser_result.metadata, merged_frontmatter)
        text_content = parser_result.text
    elif source_type == "html":
        parser_result = parse_html_document(path, max_tokens=settings.max_chunk_tokens)
        merged_frontmatter = merge_metadata(parser_result.metadata, merged_frontmatter)
        text_content = parser_result.text
    elif source_type == "pdf":
        parser_result = prepare_pdf_chunks(path, settings=settings)
        text_content = parser_result.text
    elif source_type == "transcript":
        segments = load_transcript(path)
        parser_result = prepare_transcript_chunks(segments, settings=settings)
        text_content = parser_result.text
    elif source_type == "audio":
        parser_result = parse_audio_document(
            path,
            max_tokens=settings.max_chunk_tokens,
            settings=settings,
            frontmatter=merged_frontmatter,
        )
        merged_frontmatter = merge_metadata(parser_result.metadata, merged_frontmatter)
        text_content = parser_result.text
    else:
        text_content, parsed_frontmatter = parse_text_file(path)
        merged_frontmatter = merge_metadata(parsed_frontmatter, merged_frontmatter)
        parser_result = prepare_text_chunks(text_content, settings=settings)

    if parser_result is None:
        raise UnsupportedSourceError(f"Unable to parse source type {source_type}")

    return parser_result, merged_frontmatter, text_content


def run_pipeline_for_file(
    session: Session,
    path: Path,
    frontmatter: dict[str, Any] | None = None,
    *,
    dependencies: PipelineDependencies | None = None,
) -> Document:
    """Execute the file ingestion pipeline synchronously."""

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
        sha256 = hashlib.sha256(raw_bytes).hexdigest()

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

        if source_type == "transcript":
            document = _ingest_transcript_document(
                session,
                span,
                dependencies=persistence_dependencies,
                parser_result=parser_result,
                frontmatter=merged_frontmatter,
                settings=settings,
                sha256=sha256,
                source_type="transcript",
                title=merged_frontmatter.get("title") or path.stem,
                cache_status="n/a",
                source_url=merged_frontmatter.get("source_url"),
                transcript_path=path,
                transcript_filename=path.name,
            )
            return document

        document = _ingest_text_document(
            session,
            span,
            dependencies=persistence_dependencies,
            parser_result=parser_result,
            frontmatter=merged_frontmatter,
            settings=settings,
            sha256=sha256,
            source_type=source_type,
            title=merged_frontmatter.get("title") or path.stem,
            cache_status="n/a",
            source_url=merged_frontmatter.get("source_url"),
            text_content=text_content,
            original_path=path,
        )

        return document


def run_pipeline_for_url(
    session: Session,
    url: str,
    source_type: str | None = None,
    frontmatter: dict[str, Any] | None = None,
    *,
    dependencies: PipelineDependencies | None = None,
) -> Document:
    """Ingest supported URLs into the document store."""

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

    settings, persistence_dependencies = _resolve_context(dependencies)
    with instrument_workflow(
        "ingest.transcript",
        transcript_path=str(transcript_path),
        audio_path=str(audio_path) if audio_path else None,
    ) as span:
        merged_frontmatter = merge_metadata({}, load_frontmatter(frontmatter))

        segments = load_transcript(transcript_path)
        parser_result = prepare_transcript_chunks(segments, settings=settings)

        sha256 = _hash_parser_result(parser_result)

        source_type = str(merged_frontmatter.get("source_type") or "transcript")
        title = merged_frontmatter.get("title") or transcript_path.stem

        set_span_attribute(span, "ingest.source_type", source_type)
        document = _ingest_transcript_document(
            session,
            span,
            dependencies=persistence_dependencies,
            parser_result=parser_result,
            frontmatter=merged_frontmatter,
            settings=settings,
            sha256=sha256,
            source_type=source_type,
            title=title,
            cache_status="n/a",
            source_url=merged_frontmatter.get("source_url"),
            channel=merged_frontmatter.get("channel"),
            video_id=merged_frontmatter.get("video_id"),
            duration_seconds=merged_frontmatter.get("duration_seconds"),
            transcript_path=transcript_path,
            audio_path=audio_path,
            transcript_filename=transcript_filename or transcript_path.name,
            audio_filename=audio_filename,
        )

        return document

def _refresh_creator_verse_rollups(
    session: Session, segments: Iterable[TranscriptSegment]
) -> None:
    """Backwards-compatible wrapper for legacy imports."""

    refresh_creator_verse_rollups(session, list(segments))



_WEB_FETCH_CHUNK_SIZE = 64 * 1024
build_opener = _urllib_build_opener


def _fetch_web_document(settings, url: str):
    return resilient_operation(
        lambda: fetch_web_document(settings, url, opener_factory=build_opener),
        key=f"ingest:web:{url}",
        classification="network",
        policy=ResiliencePolicy(max_attempts=3),
    )





