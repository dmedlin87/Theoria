"""Enrichment stages for ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import Enricher


@dataclass(slots=True)
class DocumentEnricher(Enricher):
    """Attach derived document metadata before persistence."""

    default_title_factory: Callable[[dict[str, Any]], str]
    name: str = "document_enricher"

    def enrich(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        frontmatter = dict(state.get("frontmatter") or {})
        metadata = dict(state.get("document_metadata") or {})
        title = frontmatter.get("title") or self.default_title_factory(state)
        metadata.setdefault("title", title)
        metadata.setdefault("source_type", state.get("source_type"))
        if "sha256" in state and "sha256" not in metadata:
            metadata["sha256"] = state["sha256"]
        return {
            "frontmatter": frontmatter,
            "title": title,
            "document_metadata": metadata,
        }


@dataclass(slots=True)
class NoopEnricher(Enricher):
    """Enricher that forwards state without modification."""

    name: str = "noop_enricher"

    def enrich(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        return {}


@dataclass(slots=True)
class VerseDetectionEnricher(Enricher):
    """Attach verse anchors and ensure audio metadata is propagated."""

    name: str = "verse_detection_enricher"

    def enrich(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        frontmatter = dict(state.get("frontmatter") or {})
        metadata = dict(state.get("document_metadata") or {})

        verse_anchors = list(state.get("verse_anchors") or ())
        transcript_segments = list(state.get("transcript_segments") or ())
        audio_metadata = dict(state.get("audio_metadata") or {})
        audio_path = state.get("audio_path")
        source_type = str(
            state.get("source_type")
            or frontmatter.get("source_type")
            or "audio"
        )

        if verse_anchors:
            frontmatter.setdefault("verse_anchors", verse_anchors)
            metadata.setdefault("verse_anchors", verse_anchors)
            context.instrumentation.set(
                "ingest.audio.verse_anchor_count",
                len(verse_anchors),
            )
        if transcript_segments:
            metadata.setdefault("transcript_segments", transcript_segments)
            context.instrumentation.set(
                "ingest.audio.segment_count",
                len(transcript_segments),
            )
        if audio_metadata:
            frontmatter.setdefault("audio_metadata", audio_metadata)
            metadata.setdefault("audio_metadata", audio_metadata)

        if "title" not in frontmatter:
            if isinstance(audio_path, Path):
                frontmatter["title"] = audio_path.stem
            elif audio_path:
                frontmatter["title"] = Path(str(audio_path)).stem
            else:
                frontmatter["title"] = "Audio Transcript"

        context.instrumentation.set("ingest.source_type", source_type)

        return {
            "frontmatter": frontmatter,
            "document_metadata": metadata,
            "source_type": source_type,
        }
