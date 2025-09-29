"""Ingestion pipeline orchestration entry points."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..core.settings import get_settings
from ..telemetry import instrument_workflow, set_span_attribute
from ..db.models import Document
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
from .network import (
    ensure_url_allowed,
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
)


@dataclass
class PipelineDependencies:
    """Runtime dependencies for the ingestion orchestrator."""

    embedding_service: EmbeddingServiceProtocol | None = None

    def for_persistence(self) -> PersistenceDependencies:
        service = self.embedding_service or get_embedding_service()
        return PersistenceDependencies(embedding_service=service)


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

    persistence_dependencies = (
        dependencies.for_persistence()
        if dependencies
        else PipelineDependencies().for_persistence()
    )

    settings = get_settings()
    with instrument_workflow(
        "ingest.file", source_path=str(path), source_name=path.name
    ) as span:
        raw_bytes = path.read_bytes()
        sha256 = hashlib.sha256(raw_bytes).hexdigest()

        merged_frontmatter = merge_metadata(
            {}, load_frontmatter(frontmatter)
        )
        source_type = detect_source_type(path, merged_frontmatter)
        set_span_attribute(span, "ingest.source_type", source_type)
        set_span_attribute(span, "ingest.cache_status", "n/a")

        parser_result, merged_frontmatter, text_content = _prepare_parser_result(
            source_type,
            path,
            frontmatter=merged_frontmatter,
            settings=settings,
        )

        chunk_count = len(parser_result.chunks)
        set_span_attribute(span, "ingest.chunk_count", chunk_count)
        set_span_attribute(span, "ingest.batch_size", min(chunk_count, 32))

        if source_type == "transcript":
            document = persist_transcript_document(
                session,
                dependencies=persistence_dependencies,
                chunks=parser_result.chunks,
                parser=parser_result.parser,
                parser_version=parser_result.parser_version,
                frontmatter=merged_frontmatter,
                settings=settings,
                sha256=sha256,
                source_type="transcript",
                title=merged_frontmatter.get("title") or path.stem,
                source_url=merged_frontmatter.get("source_url"),
                transcript_path=path,
                transcript_filename=path.name,
            )
            set_span_attribute(span, "ingest.document_id", document.id)
            return document

        document = persist_text_document(
            session,
            dependencies=persistence_dependencies,
            chunks=parser_result.chunks,
            parser=parser_result.parser,
            parser_version=parser_result.parser_version,
            frontmatter=merged_frontmatter,
            settings=settings,
            sha256=sha256,
            source_type=source_type,
            title=merged_frontmatter.get("title") or path.stem,
            source_url=merged_frontmatter.get("source_url"),
            text_content=text_content,
            original_path=path,
        )
        set_span_attribute(span, "ingest.document_id", document.id)
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

    persistence_dependencies = (
        dependencies.for_persistence()
        if dependencies
        else PipelineDependencies().for_persistence()
    )

    settings = get_settings()
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
            sha_payload = "\n".join(chunk.text for chunk in parser_result.chunks).encode(
                "utf-8"
            )
            sha256 = hashlib.sha256(sha_payload).hexdigest()

            chunk_count = len(parser_result.chunks)
            set_span_attribute(span, "ingest.chunk_count", chunk_count)
            set_span_attribute(span, "ingest.batch_size", min(chunk_count, 32))
            cache_status = "hit" if transcript_path else "miss"
            set_span_attribute(span, "ingest.cache_status", cache_status)
            if transcript_path:
                set_span_attribute(span, "ingest.transcript_fixture", transcript_path.name)

            document = persist_transcript_document(
                session,
                dependencies=persistence_dependencies,
                chunks=parser_result.chunks,
                parser=parser_result.parser,
                parser_version=parser_result.parser_version,
                frontmatter=merged_frontmatter,
                settings=settings,
                sha256=sha256,
                source_type="youtube",
                title=merged_frontmatter.get("title")
                or metadata.get("title")
                or f"YouTube Video {video_id}",
                source_url=merged_frontmatter.get("source_url") or url,
                channel=merged_frontmatter.get("channel") or metadata.get("channel"),
                video_id=video_id,
                duration_seconds=merged_frontmatter.get("duration_seconds")
                or metadata.get("duration_seconds"),
                transcript_path=transcript_path,
                transcript_filename=(transcript_path.name if transcript_path else None),
            )
            set_span_attribute(span, "ingest.document_id", document.id)
            return document

        if resolved_source_type not in {"web_page", "html", "website"}:
            raise UnsupportedSourceError(
                (
                    "Unsupported source type for URL ingestion: "
                    f"{resolved_source_type}. Supported types are: "
                    "youtube, web_page, html, website"
                )
            )

        html, metadata = fetch_web_document(settings, url)
        text_content = html_to_text(html)
        if not text_content:
            raise UnsupportedSourceError("Fetched HTML did not contain extractable text")

        merged_frontmatter = merge_metadata(metadata, load_frontmatter(frontmatter))
        parser_result = prepare_text_chunks(text_content, settings=settings)
        sha_payload = "\n".join(chunk.text for chunk in parser_result.chunks).encode("utf-8")
        sha256 = hashlib.sha256(sha_payload).hexdigest()

        chunk_count = len(parser_result.chunks)
        set_span_attribute(span, "ingest.chunk_count", chunk_count)
        set_span_attribute(span, "ingest.batch_size", min(chunk_count, 32))
        set_span_attribute(span, "ingest.cache_status", "n/a")

        document = persist_text_document(
            session,
            dependencies=persistence_dependencies,
            chunks=parser_result.chunks,
            parser=parser_result.parser,
            parser_version=parser_result.parser_version,
            frontmatter=merged_frontmatter,
            settings=settings,
            sha256=sha256,
            source_type="web_page",
            title=merged_frontmatter.get("title") or metadata.get("title") or url,
            source_url=merged_frontmatter.get("source_url")
            or metadata.get("canonical_url")
            or url,
            text_content=parser_result.text,
            raw_content=html,
            raw_filename="source.html",
        )
        set_span_attribute(span, "ingest.document_id", document.id)
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

    persistence_dependencies = (
        dependencies.for_persistence()
        if dependencies
        else PipelineDependencies().for_persistence()
    )

    settings = get_settings()
    with instrument_workflow(
        "ingest.transcript",
        transcript_path=str(transcript_path),
        audio_path=str(audio_path) if audio_path else None,
    ) as span:
        merged_frontmatter = merge_metadata({}, load_frontmatter(frontmatter))

        segments = load_transcript(transcript_path)
        parser_result = prepare_transcript_chunks(segments, settings=settings)

        sha_payload = "\n".join(chunk.text for chunk in parser_result.chunks).encode(
            "utf-8"
        )
        sha256 = hashlib.sha256(sha_payload).hexdigest()

        source_type = str(merged_frontmatter.get("source_type") or "transcript")
        title = merged_frontmatter.get("title") or transcript_path.stem

        chunk_count = len(parser_result.chunks)
        set_span_attribute(span, "ingest.source_type", source_type)
        set_span_attribute(span, "ingest.chunk_count", chunk_count)
        set_span_attribute(span, "ingest.batch_size", min(chunk_count, 32))
        set_span_attribute(span, "ingest.cache_status", "n/a")

        document = persist_transcript_document(
            session,
            dependencies=persistence_dependencies,
            chunks=parser_result.chunks,
            parser=parser_result.parser,
            parser_version=parser_result.parser_version,
            frontmatter=merged_frontmatter,
            settings=settings,
            sha256=sha256,
            source_type=source_type,
            title=title,
            source_url=merged_frontmatter.get("source_url"),
            channel=merged_frontmatter.get("channel"),
            video_id=merged_frontmatter.get("video_id"),
            duration_seconds=merged_frontmatter.get("duration_seconds"),
            transcript_path=transcript_path,
            audio_path=audio_path,
            transcript_filename=transcript_filename or transcript_path.name,
            audio_filename=audio_filename,
        )
        set_span_attribute(span, "ingest.document_id", document.id)
        return document

