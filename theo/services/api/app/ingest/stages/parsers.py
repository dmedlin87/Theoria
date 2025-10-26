"""Parser stages for ingestion orchestrations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..exceptions import UnsupportedSourceError
from ..metadata import (
    ensure_list,
    html_to_text,
    merge_metadata,
    parse_text_file,
    prepare_pdf_chunks,
    prepare_text_chunks,
    prepare_transcript_chunks,
)
from ..osis import OsisDocument, ResolvedCommentaryAnchor
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

    def parse(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
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

    def parse(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
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

    def parse(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
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

    def parse(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        source_type = state.get("source_type")
        if source_type == "youtube":
            return self.transcript_parser.parse(context=context, state=state)
        return self.web_parser.parse(context=context, state=state)


@dataclass(slots=True)
class OsisCommentaryParser(Parser):
    """Resolve commentary anchors from OSIS documents."""

    name: str = "osis_commentary_parser"

    def parse(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        document: OsisDocument = state["osis_document"]
        frontmatter = dict(state.get("frontmatter") or {})

        default_source = (
            frontmatter.get("source")
            or frontmatter.get("commentary_source")
            or document.metadata.get("source")
            or document.work
            or "community"
        )
        perspective_raw = (
            frontmatter.get("perspective")
            or frontmatter.get("commentary_perspective")
            or "neutral"
        )
        default_perspective = str(perspective_raw).strip().lower() or "neutral"
        tag_source = frontmatter.get("tags") or frontmatter.get("commentary_tags")
        default_tags = ensure_list(tag_source) or None

        entries: list[ResolvedCommentaryAnchor] = []
        seen: set[tuple[str, str]] = set()
        anchor_counts: dict[str, int] = {}

        for commentary in document.commentaries:
            excerpt = commentary.excerpt.strip()
            if not excerpt or not commentary.anchors:
                continue
            title = commentary.title or document.title
            for anchor in commentary.anchors:
                key = (anchor, excerpt)
                if key in seen:
                    continue
                seen.add(key)
                index = anchor_counts.get(anchor, 0)
                anchor_counts[anchor] = index + 1
                note_identifier = commentary.note_id or f"{anchor}#{index}"
                entries.append(
                    ResolvedCommentaryAnchor(
                        osis=anchor,
                        excerpt=excerpt,
                        title=title,
                        perspective=default_perspective,
                        source=default_source,
                        tags=default_tags,
                        note_id=note_identifier,
                    )
                )

        if not entries:
            raise UnsupportedSourceError(
                "OSIS payload did not contain any commentary anchors"
            )

        frontmatter.setdefault("source_type", "osis")
        if document.work and "osis_work" not in frontmatter:
            frontmatter["osis_work"] = document.work
        if document.title and "title" not in frontmatter:
            frontmatter["title"] = document.title

        instrumentation = context.instrumentation
        instrumentation.set("ingest.commentary_entries", len(entries))

        return {
            "commentary_entries": entries,
            "frontmatter": frontmatter,
        }


@dataclass(slots=True)
class AudioTranscriptionParser(Parser):
    """Transcribe audio using Whisper and detect verses."""

    name: str = "audio_transcription_parser"

    def parse(self, *, context: Any, state: dict[str, Any]) -> dict[str, Any]:
        audio_path = state["audio_path"]
        frontmatter = state.get("frontmatter", {})

        # Transcribe audio
        transcript_segments = self._transcribe_audio(
            audio_path, context.settings
        )
        
        # Detect scripture references
        verse_anchors = self._detect_scripture_references(
            transcript_segments, context.settings
        )

        # Prepare searchable chunks
        parser_result = prepare_transcript_chunks(
            transcript_segments, settings=context.settings
        )
        
        return {
            "parser_result": parser_result,
            "transcript_segments": transcript_segments,
            "verse_anchors": verse_anchors,
            "frontmatter": frontmatter,
        }

    def _transcribe_audio(self, audio_path: Path, settings) -> list[dict]:
        """Transcribe audio using Whisper model."""
        try:
            import whisper
        except ImportError:
            raise RuntimeError(
                "Whisper not installed. Run 'pip install -U openai-whisper'"
            )
            
        # Load model based on settings
        model_size = getattr(settings, "whisper_model_size", "base")
        device = getattr(settings, "whisper_device", "cpu")
        model = whisper.load_model(model_size, device=device)
        
        # Transcribe audio
        result = model.transcribe(
            str(audio_path),
            verbose=False,
            language="en",
            fp16=False if device == "cpu" else True
        )
        
        # Format segments
        segments = []
        for seg in result["segments"]:
            speech_confidence = 1.0 - float(seg.get("no_speech_prob", 0.0))
            segments.append(
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"].strip(),
                    "confidence": max(0.0, min(1.0, speech_confidence)),
                }
            )
            
        return segments

    def _detect_scripture_references(self, segments, settings) -> list[dict]:
        """Detect scripture references in transcript."""
        try:
            from transformers import pipeline
        except ImportError:
            raise RuntimeError("Verse detection requires transformers library")
            
        # Combine segments into full text
        full_text = " ".join(seg["text"] for seg in segments)
        
        # Load model
        model_name = getattr(settings, "verse_detection_model", "biblical-ai/verse-detection-bert")
        detector = pipeline(
            "token-classification",
            model=model_name,
            aggregation_strategy="simple",
            device=getattr(settings, "verse_detection_device", "cpu")
        )
        
        # Detect verses
        results = detector(full_text)
        
        # Format and filter
        verse_anchors = []
        for res in results:
            if res["entity_group"] == "VERSE":
                verse_anchors.append({
                    "verse": res["word"],
                    "confidence": res["score"],
                    "start_index": res["start"],
                    "end_index": res["end"]
                })
        
        return verse_anchors
