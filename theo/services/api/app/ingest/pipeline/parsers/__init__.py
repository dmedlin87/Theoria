"""Parser utilities for the ingestion pipeline."""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from ..chunking import chunk_text, chunk_transcript
from ..parsers import (
    PDF_EXTRACTION_UNSUPPORTED,
    ParserResult,
    TranscriptSegment as ParsedTranscriptSegment,
    load_transcript,
    parse_audio_document,
    parse_docx_document,
    parse_html_document,
    parse_pdf_document,
    read_text_file,
)
from .exceptions import UnsupportedSourceError


class HTMLMetadataParser(HTMLParser):
    """Parse minimal metadata from an HTML page."""

    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self.canonical_url: str | None = None
        self._capture_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name == "title":
            self._capture_title = True
            return

        attr_map = {key.lower(): (value or "") for key, value in attrs}
        if name == "link":
            rel = attr_map.get("rel", "")
            rel_values = {item.strip().lower() for item in rel.split() if item}
            if "canonical" in rel_values and not self.canonical_url:
                href = attr_map.get("href")
                if href:
                    self.canonical_url = href.strip()
        elif name == "meta":
            prop = attr_map.get("property") or attr_map.get("name") or ""
            prop_lower = prop.lower()
            content = attr_map.get("content")
            if content:
                content = content.strip()
            if not content:
                return
            if prop_lower == "og:title" and not self.title:
                self.title = content
            if prop_lower in {"og:url", "twitter:url"} and not self.canonical_url:
                self.canonical_url = content

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._capture_title = False

    def handle_data(self, data: str) -> None:
        if not self._capture_title:
            return
        text = data.strip()
        if text and not self.title:
            self.title = text


class HTMLTextExtractor(HTMLParser):
    """Convert HTML into a normalized text representation."""

    _BLOCK_TAGS = {
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "p",
        "pre",
        "section",
        "summary",
        "ul",
        "ol",
    }

    _SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if lower == "br":
            self._emit_newline()
        elif lower in self._BLOCK_TAGS:
            self._emit_paragraph_break()

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in self._SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if lower in self._BLOCK_TAGS and lower != "br":
            self._emit_paragraph_break()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = unescape(data)
        if not text.strip():
            return
        if self._parts and not self._parts[-1].endswith((" ", "\n")):
            self._parts.append(" ")
        self._parts.append(text.strip())

    def _emit_newline(self) -> None:
        if self._parts and not self._parts[-1].endswith("\n"):
            self._parts.append("\n")

    def _emit_paragraph_break(self) -> None:
        if not self._parts:
            return
        if not self._parts[-1].endswith("\n\n"):
            if self._parts[-1].endswith("\n"):
                self._parts.append("\n")
            else:
                self._parts.append("\n\n")

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def parse_html_metadata(html: str) -> dict[str, str | None]:
    parser = HTMLMetadataParser()
    parser.feed(html)
    parser.close()
    return {"title": parser.title, "canonical_url": parser.canonical_url}


def html_to_text(html: str) -> str:
    extractor = HTMLTextExtractor()
    extractor.feed(html)
    extractor.close()
    return extractor.get_text()


def prepare_text_chunks(text: str, *, settings) -> ParserResult:
    chunks = chunk_text(text, max_tokens=settings.max_chunk_tokens)
    return ParserResult(text=text, chunks=chunks, parser="plain_text", parser_version="0.1.0")


def prepare_pdf_chunks(path: Path, *, settings) -> ParserResult:
    result = parse_pdf_document(
        path,
        max_pages=settings.doc_max_pages,
        max_tokens=settings.max_chunk_tokens,
    )
    if result is PDF_EXTRACTION_UNSUPPORTED:
        raise UnsupportedSourceError(
            "Unable to extract text from PDF; the file may be password protected or corrupted."
        )
    if not result.chunks:
        raise UnsupportedSourceError("PDF contained no extractable text")
    return result


def prepare_transcript_chunks(
    segments: list[ParsedTranscriptSegment],
    *,
    settings,
) -> ParserResult:
    if not segments:
        raise UnsupportedSourceError("Transcript contained no segments")

    chunks = chunk_transcript(
        segments,
        max_tokens=settings.max_chunk_tokens,
        max_window_seconds=getattr(settings, "transcript_max_window", 40.0),
    )
    text = " ".join(segment.text for segment in segments)
    return ParserResult(
        text=text, chunks=chunks, parser="transcript", parser_version="0.3.0"
    )


__all__ = [
    "HTMLMetadataParser",
    "HTMLTextExtractor",
    "html_to_text",
    "load_transcript",
    "parse_audio_document",
    "parse_docx_document",
    "parse_html_document",
    "parse_pdf_document",
    "ParsedTranscriptSegment",
    "ParserResult",
    "PDF_EXTRACTION_UNSUPPORTED",
    "prepare_pdf_chunks",
    "prepare_text_chunks",
    "prepare_transcript_chunks",
    "read_text_file",
    "parse_html_metadata",
]
