"""Concrete implementations of ingestion source fetch stages."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..exceptions import UnsupportedSourceError
from ..metadata import detect_source_type, load_frontmatter, merge_metadata
from ..osis import parse_osis_document
from ..network import (
    extract_youtube_video_id,
    fetch_web_document,
    is_youtube_url,
    load_youtube_metadata,
    load_youtube_transcript,
)
from .. import network as ingest_network
from . import Instrumentation, SourceFetcher


@dataclass(slots=True)
class FileSourceFetcher(SourceFetcher):
    """Load a local file from disk for ingestion."""

    path: Path
    frontmatter: dict[str, Any]
    name: str = "file_source_fetcher"

    def fetch(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        instrumentation: Instrumentation = context.instrumentation
        raw_bytes = self.path.read_bytes()
        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        merged_frontmatter = merge_metadata({}, load_frontmatter(self.frontmatter))
        source_type = detect_source_type(self.path, merged_frontmatter)
        instrumentation.set("ingest.source_type", source_type)
        return {
            "path": self.path,
            "raw_bytes": raw_bytes,
            "sha256": sha256,
            "source_type": source_type,
            "frontmatter": merged_frontmatter,
            "cache_status": "n/a",
            "document_metadata": {
                "sha256": sha256,
                "source_type": source_type,
                "origin": str(self.path),
            },
        }


@dataclass(slots=True)
class UrlSourceFetcher(SourceFetcher):
    """Fetch web documents and associated metadata."""

    url: str
    source_type: str | None
    frontmatter: dict[str, Any]
    ensure_url_allowed_fn: Callable[[Any, str], None] | None = None
    fetch_document_fn: Callable[[Any, str], tuple[str, dict[str, Any]]] | None = None
    name: str = "url_source_fetcher"

    def fetch(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        instrumentation: Instrumentation = context.instrumentation
        settings = context.settings
        merged_frontmatter = merge_metadata({}, load_frontmatter(self.frontmatter))

        ensure_callable = self.ensure_url_allowed_fn or ingest_network.ensure_url_allowed
        ensure_callable(settings, self.url)

        resolved_source_type = self.source_type or (
            "youtube" if is_youtube_url(self.url) else "web_page"
        )
        instrumentation.set("ingest.source_type", resolved_source_type)

        if resolved_source_type == "youtube":
            video_id = extract_youtube_video_id(self.url)
            metadata = load_youtube_metadata(settings, video_id)
            merged_frontmatter = merge_metadata(metadata, merged_frontmatter)
            segments, transcript_path = load_youtube_transcript(settings, video_id)
            cache_status = "hit" if transcript_path else "miss"
            if transcript_path:
                instrumentation.set(
                    "ingest.transcript_fixture", transcript_path.name
                )
            return {
                "frontmatter": merged_frontmatter,
                "segments": segments,
                "transcript_path": transcript_path,
                "video_id": video_id,
                "source_type": "youtube",
                "cache_status": cache_status,
                "url": self.url,
                "document_metadata": {
                    "source_type": "youtube",
                    "video_id": video_id,
                    "origin": self.url,
                    "cache_status": cache_status,
                },
            }

        if resolved_source_type not in {"web_page", "html", "website"}:
            raise UnsupportedSourceError(
                "Unsupported source type for URL ingestion: "
                f"{resolved_source_type}. Supported types are: youtube, web_page, html, website"
            )

        fetch_callable = self.fetch_document_fn or fetch_web_document
        html, metadata = fetch_callable(settings, self.url)
        merged_frontmatter = merge_metadata(metadata, merged_frontmatter)
        return {
            "frontmatter": merged_frontmatter,
            "html": html,
            "source_type": "web_page",
            "url": self.url,
            "cache_status": "n/a",
            "raw_filename": "source.html",
            "document_metadata": {
                "source_type": "web_page",
                "origin": self.url,
            },
        }


@dataclass(slots=True)
class TranscriptSourceFetcher(SourceFetcher):
    """Fetch transcripts stored on disk, optionally with audio."""

    transcript_path: Path
    frontmatter: dict[str, Any]
    audio_path: Path | None = None
    transcript_filename: str | None = None
    audio_filename: str | None = None
    name: str = "transcript_source_fetcher"

    def fetch(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        merged_frontmatter = merge_metadata({}, load_frontmatter(self.frontmatter))
        return {
            "transcript_path": self.transcript_path,
            "frontmatter": merged_frontmatter,
            "audio_path": self.audio_path,
            "transcript_filename": self.transcript_filename,
            "audio_filename": self.audio_filename,
            "source_type": str(
                merged_frontmatter.get("source_type") or "transcript"
            ),
            "cache_status": "n/a",
            "document_metadata": {
                "origin": str(self.transcript_path),
                "source_type": str(
                    merged_frontmatter.get("source_type") or "transcript"
                ),
            },
        }


@dataclass(slots=True)
class OsisSourceFetcher(SourceFetcher):
    """Load an OSIS/XML payload and normalise its structure."""

    path: Path
    frontmatter: dict[str, Any]
    name: str = "osis_source_fetcher"

    def fetch(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        instrumentation: Instrumentation = context.instrumentation
        raw_bytes = self.path.read_bytes()
        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        xml_text = raw_bytes.decode("utf-8", errors="replace")
        document = parse_osis_document(xml_text)
        merged_frontmatter = merge_metadata({}, load_frontmatter(self.frontmatter))
        instrumentation.set("ingest.source_type", "osis")
        instrumentation.set("ingest.osis_commentary_count", len(document.commentaries))
        instrumentation.set("ingest.osis_verse_count", len(document.verses))
        metadata = {
            "sha256": sha256,
            "source_type": "osis",
            "origin": str(self.path),
        }
        if document.work:
            metadata["osis_work"] = document.work
        return {
            "path": self.path,
            "raw_bytes": raw_bytes,
            "sha256": sha256,
            "frontmatter": merged_frontmatter,
            "osis_document": document,
            "source_type": "osis",
            "raw_content": xml_text,
            "raw_filename": self.path.name,
            "document_metadata": metadata,
        }
