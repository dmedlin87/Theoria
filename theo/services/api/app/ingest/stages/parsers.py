"""Parser stages for ingestion orchestrations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..metadata import (
    merge_metadata,
    prepare_pdf_chunks,
    prepare_text_chunks,
    prepare_transcript_chunks,
)
from ..exceptions import UnsupportedSourceError
from ..metadata import html_to_text, parse_text_file
from ..parsers import (
    ParserResult,
    load_transcript,
    parse_audio_document,
    parse_docx_document,
    parse_html_document,
)
from . import Parser


def _hash_parser_result(parser_result: ParserResult) -> str:
    payload = "\n".join(chunk.text for chunk in parser_result.chunks).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(slots=True)
class FileParser(Parser):
    """Parse local files based on detected source types."""

    name: str = "file_parser"

    def parse(self, *, context, state: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        settings = context.settings
        source_type = state["source_type"]
        path: Path = state["path"]
        frontmatter = dict(state.get("frontmatter") or {})
        parser_result: ParserResult | None = None
        text_content = ""

        if source_type in {"markdown", "txt", "file"}:
            text_content, parsed_frontmatter = parse_text_file(path)
            frontmatter = merge_metadata(parsed_frontmatter, frontmatter)
            parser_result = prepare_text_chunks(text_content, settings=settings)
        elif source_type == "docx":
            parser_result = parse_docx_document(path, max_tokens=settings.max_chunk_tokens)
            frontmatter = merge_metadata(parser_result.metadata, frontmatter)
            text_content = parser_result.text
        elif source_type == "html":
            parser_result = parse_html_document(path, max_tokens=settings.max_chunk_tokens)
            frontmatter = merge_metadata(parser_result.metadata, frontmatter)
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
                frontmatter=frontmatter,
            )
            frontmatter = merge_metadata(parser_result.metadata, frontmatter)
            text_content = parser_result.text
        else:
            text_content, parsed_frontmatter = parse_text_file(path)
            frontmatter = merge_metadata(parsed_frontmatter, frontmatter)
            parser_result = prepare_text_chunks(text_content, settings=settings)

        if parser_result is None:
            raise UnsupportedSourceError(
                f"Unable to parse source type {source_type}"
            )

        return {
            "parser_result": parser_result,
            "frontmatter": frontmatter,
            "text_content": text_content,
        }


@dataclass(slots=True)
class WebPageParser(Parser):
    """Parse fetched HTML payloads."""

    name: str = "web_page_parser"

    def parse(self, *, context, state: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        settings = context.settings
        html: str = state["html"]
        text_content = html_to_text(html)
        if not text_content:
            raise UnsupportedSourceError(
                "Fetched HTML did not contain extractable text"
            )
        parser_result = prepare_text_chunks(text_content, settings=settings)
        sha256 = _hash_parser_result(parser_result)
        metadata = dict(state.get("document_metadata") or {})
        metadata.setdefault("sha256", sha256)
        return {
            "parser_result": parser_result,
            "text_content": text_content,
            "sha256": sha256,
            "document_metadata": metadata,
        }


@dataclass(slots=True)
class TranscriptParser(Parser):
    """Parse transcript segments from fetchers or disk."""

    name: str = "transcript_parser"

    def parse(self, *, context, state: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        settings = context.settings
        segments = state.get("segments")
        if segments is None:
            transcript_path: Path = state["transcript_path"]
            segments = load_transcript(transcript_path)
        parser_result = prepare_transcript_chunks(segments, settings=settings)
        sha256 = _hash_parser_result(parser_result)
        metadata = dict(state.get("document_metadata") or {})
        metadata.setdefault("sha256", sha256)
        return {
            "parser_result": parser_result,
            "text_content": parser_result.text,
            "sha256": sha256,
            "document_metadata": metadata,
        }


@dataclass(slots=True)
class UrlParser(Parser):
    """Delegate to transcript or web parsers based on fetched state."""

    name: str = "url_parser"
    transcript_parser: TranscriptParser = field(default_factory=TranscriptParser)
    web_parser: WebPageParser = field(default_factory=WebPageParser)

    def parse(self, *, context, state: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        source_type = state.get("source_type")
        if source_type == "youtube":
            return self.transcript_parser.parse(context=context, state=state)
        return self.web_parser.parse(context=context, state=state)
