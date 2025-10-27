"""Persister stages bridging orchestration and database helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..exceptions import UnsupportedSourceError
from ..persistence import (
    CommentaryImportResult,
    persist_commentary_entries,
    persist_text_document,
    persist_transcript_document,
)
from . import Persister


def _set_chunk_metrics(context: Any, parser_result: Any) -> None:
    chunk_count = len(parser_result.chunks)
    context.instrumentation.set("ingest.chunk_count", chunk_count)
    context.instrumentation.set("ingest.batch_size", min(chunk_count, 32))


@dataclass(slots=True)
class TextDocumentPersister(Persister):
    """Persist text-based documents."""

    session: Session
    name: str = "text_document_persister"

    def persist(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        parser_result = state["parser_result"]
        _set_chunk_metrics(context, parser_result)
        cache_status = state.get("cache_status")
        if cache_status is not None:
            context.instrumentation.set("ingest.cache_status", cache_status)

        frontmatter = dict(state.get("frontmatter") or {})
        metadata = dict(state.get("document_metadata") or {})
        sha256 = state.get("sha256") or metadata.get("sha256")
        if not sha256:
            raise ValueError("sha256 missing from orchestration state")

        document = persist_text_document(
            self.session,
            context=context,
            chunks=parser_result.chunks,
            parser=parser_result.parser,
            parser_version=parser_result.parser_version,
            frontmatter=frontmatter,
            sha256=sha256,
            source_type=str(state.get("source_type") or frontmatter.get("source_type") or "file"),
            title=state.get("title"),
            source_url=(
                state.get("source_url")
                or frontmatter.get("source_url")
                or state.get("url")
            ),
            text_content=state.get("text_content", parser_result.text),
            original_path=state.get("path"),
            raw_content=state.get("html") or state.get("raw_content"),
            raw_filename=state.get("raw_filename"),
        )
        context.instrumentation.set("ingest.document_id", document.id)
        metadata.setdefault("document_id", document.id)
        return {
            "document": document,
            "document_metadata": metadata,
        }


@dataclass(slots=True)
class TranscriptDocumentPersister(Persister):
    """Persist transcript based documents."""

    session: Session
    name: str = "transcript_document_persister"

    def persist(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        parser_result = state["parser_result"]
        _set_chunk_metrics(context, parser_result)
        cache_status = state.get("cache_status")
        if cache_status is not None:
            context.instrumentation.set("ingest.cache_status", cache_status)

        frontmatter = dict(state.get("frontmatter") or {})
        metadata = dict(state.get("document_metadata") or {})
        sha256 = state.get("sha256") or metadata.get("sha256")
        if not sha256:
            raise ValueError("sha256 missing from orchestration state")

        document = persist_transcript_document(
            self.session,
            context=context,
            chunks=parser_result.chunks,
            parser=parser_result.parser,
            parser_version=parser_result.parser_version,
            frontmatter=frontmatter,
            sha256=sha256,
            source_type=str(state.get("source_type") or frontmatter.get("source_type") or "transcript"),
            title=str(state.get("title") or frontmatter.get("title") or "Transcript"),
            source_url=(
                state.get("source_url")
                or frontmatter.get("source_url")
                or state.get("url")
            ),
            channel=frontmatter.get("channel"),
            video_id=frontmatter.get("video_id") or state.get("video_id"),
            duration_seconds=frontmatter.get("duration_seconds"),
            transcript_path=state.get("transcript_path"),
            audio_path=state.get("audio_path"),
            transcript_filename=state.get("transcript_filename"),
            audio_filename=state.get("audio_filename"),
        )
        context.instrumentation.set("ingest.document_id", document.id)
        metadata.setdefault("document_id", document.id)
        return {
            "document": document,
            "document_metadata": metadata,
        }


@dataclass(slots=True)
class AudioDocumentPersister(Persister):
    """Persist audio-derived transcripts and metadata."""

    session: Session
    name: str = "audio_document_persister"

    def persist(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        parser_result = state["parser_result"]
        _set_chunk_metrics(context, parser_result)
        cache_status = state.get("cache_status")
        if cache_status is not None:
            context.instrumentation.set("ingest.cache_status", cache_status)

        frontmatter = dict(state.get("frontmatter") or {})
        metadata = dict(state.get("document_metadata") or {})
        audio_path = state.get("audio_path")
        audio_metadata = dict(state.get("audio_metadata") or {})
        verse_anchors = list(state.get("verse_anchors") or ())
        transcript_segments = list(state.get("transcript_segments") or ())

        if audio_metadata:
            frontmatter.setdefault("audio_metadata", audio_metadata)
            metadata.setdefault("audio_metadata", audio_metadata)
        if verse_anchors:
            frontmatter.setdefault("verse_anchors", verse_anchors)
            metadata.setdefault("verse_anchors", verse_anchors)
        if transcript_segments:
            metadata.setdefault("transcript_segments", transcript_segments)

        sha256 = state.get("sha256") or metadata.get("sha256")
        if not sha256:
            raise ValueError("sha256 missing from orchestration state")

        title = (
            frontmatter.get("title")
            or metadata.get("title")
            or (audio_path.stem if isinstance(audio_path, Path) else None)
            or "Audio Transcript"
        )

        source_type = str(
            state.get("source_type")
            or frontmatter.get("source_type")
            or "audio"
        )

        document = persist_transcript_document(
            self.session,
            context=context,
            chunks=parser_result.chunks,
            parser=parser_result.parser,
            parser_version=parser_result.parser_version,
            frontmatter=frontmatter,
            sha256=sha256,
            source_type=source_type,
            title=title,
            source_url=(
                state.get("source_url")
                or frontmatter.get("source_url")
                or metadata.get("source_url")
            ),
            channel=frontmatter.get("channel"),
            video_id=frontmatter.get("video_id"),
            duration_seconds=audio_metadata.get("duration_seconds"),
            transcript_path=state.get("transcript_path"),
            audio_path=audio_path,
            transcript_filename=state.get("transcript_filename"),
            audio_filename=state.get("audio_filename"),
        )
        context.instrumentation.set("ingest.document_id", document.id)
        metadata.setdefault("document_id", document.id)
        return {
            "document": document,
            "document_metadata": metadata,
        }


@dataclass(slots=True)
class CommentarySeedPersister(Persister):
    """Persist commentary excerpts derived from OSIS imports."""

    session: Session
    name: str = "commentary_seed_persister"

    def persist(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        entries = state.get("commentary_entries")
        if not entries:
            raise UnsupportedSourceError("No commentary entries available for persistence")
        result: CommentaryImportResult = persist_commentary_entries(
            self.session,
            entries=entries,
        )
        instrumentation = context.instrumentation
        instrumentation.set("ingest.commentary_inserted", result.inserted)
        instrumentation.set("ingest.commentary_updated", result.updated)
        instrumentation.set("ingest.commentary_skipped", result.skipped)
        return {
            "commentary_result": result,
            "commentary_record_ids": [r.id for r in result.records],
        }
