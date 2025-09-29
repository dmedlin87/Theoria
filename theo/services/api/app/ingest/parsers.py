"""Lightweight content parsers for ingestion pipeline."""

from __future__ import annotations

import inspect
import json
import re
import wave
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

import webvtt
from pdfminer.high_level import extract_text
from pdfminer.pdfdocument import (
    PDFNoValidXRef,
    PDFPasswordIncorrect,
    PDFTextExtractionNotAllowed,
)
from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.psparser import PSEOF

if TYPE_CHECKING:  # pragma: no cover - import-cycle guard
    from .chunking import Chunk


@dataclass(slots=True)
class ParsedPage:
    text: str
    page_no: int | None = None


@dataclass(slots=True)
class TranscriptSegment:
    text: str
    start: float
    end: float
    speaker: str | None = None


@dataclass(slots=True)
class ParserResult:
    """Normalized parser output consumed by the pipeline."""

    text: str
    chunks: list["Chunk"]
    parser: str
    parser_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fallback to a lossy decode so ingestion can continue with replacement
        # characters instead of failing hard on unexpected encodings.
        return path.read_text(encoding="utf-8", errors="replace")


class _PdfExtractionErrorSentinel:
    """Sentinel returned when pdfminer cannot extract text."""

    __slots__ = ()


PDF_EXTRACTION_UNSUPPORTED = _PdfExtractionErrorSentinel()


def parse_pdf(path: Path, *, max_pages: int | None = None) -> list[ParsedPage] | _PdfExtractionErrorSentinel:
    """Extract text from a PDF file page-by-page using pdfminer."""

    pages: list[ParsedPage] = []
    page_index = 0
    while True:
        if max_pages is not None and page_index >= max_pages:
            break
        try:
            text = extract_text(str(path), page_numbers=[page_index])
        except (
            PDFPasswordIncorrect,
            PDFTextExtractionNotAllowed,
            PDFSyntaxError,
            PDFNoValidXRef,
            PSEOF,
        ):
            return PDF_EXTRACTION_UNSUPPORTED
        if not text:
            break
        cleaned = "\n".join(line.rstrip() for line in text.splitlines()).strip()
        pages.append(ParsedPage(text=cleaned, page_no=page_index + 1))
        page_index += 1
    return pages


def parse_transcript_vtt(path: Path) -> list[TranscriptSegment]:
    """Parse a WebVTT transcript file into structured segments."""

    segments: list[TranscriptSegment] = []
    for entry in webvtt.read(str(path)):
        text = " ".join(entry.text.split())
        if not text:
            continue

        speaker: str | None = None
        if ":" in text:
            potential, remainder = text.split(":", 1)
            if (
                potential.strip().istitle()
                or potential.strip().startswith("Speaker")
                or potential.strip().endswith("Narrator")
            ):
                speaker = potential.strip()
                text = remainder.strip()

        segments.append(
            TranscriptSegment(
                text=text,
                start=float(entry.start_in_seconds),
                end=float(entry.end_in_seconds),
                speaker=speaker,
            )
        )
    return segments


def parse_transcript_json(path: Path) -> list[TranscriptSegment]:
    """Parse a JSON transcript array."""

    payload = json.loads(read_text_file(path))
    segments: list[TranscriptSegment] = []
    if isinstance(payload, dict) and "events" in payload:
        payload = payload["events"]
    if not isinstance(payload, list):
        return segments
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        start = float(item.get("start", 0.0))
        duration = item.get("duration")
        if duration is not None:
            end = start + float(duration)
        else:
            end = float(item.get("end", start))
        segments.append(
            TranscriptSegment(
                text=text,
                start=start,
                end=end,
                speaker=item.get("speaker"),
            )
        )
    return segments


def load_transcript(path: Path) -> list[TranscriptSegment]:
    suffix = path.suffix.lower()
    if suffix in {".vtt", ".webvtt"}:
        return parse_transcript_vtt(path)
    if suffix == ".srt":
        vtt = webvtt.from_srt(str(path))
        segments: list[TranscriptSegment] = []
        for entry in vtt:
            text = " ".join(entry.text.split())
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    text=text,
                    start=float(entry.start_in_seconds),
                    end=float(entry.end_in_seconds),
                )
            )
        return segments
    if suffix == ".json":
        return parse_transcript_json(path)
    raise ValueError(f"Unsupported transcript format: {suffix}")


def _package_version(distribution: str, fallback: str) -> str:
    try:
        return importlib_metadata.version(distribution)
    except importlib_metadata.PackageNotFoundError:
        return fallback
    except Exception:  # pragma: no cover - defensive
        return fallback


def _docling_extract_text(path: Path) -> tuple[str, dict[str, Any]] | None:
    try:
        from docling.document_converter import DocumentConverter
    except Exception:  # pragma: no cover - dependency optional
        return None

    try:
        converter = DocumentConverter()
        result = converter.convert(str(path))
    except Exception:  # pragma: no cover - runtime safety
        return None

    document = getattr(result, "document", None)
    if document is None:
        return None

    text = ""
    for attr in ("export_to_markdown", "export_to_text", "as_text"):
        exporter = getattr(document, attr, None)
        if callable(exporter):
            try:
                exported = exporter()
            except Exception:  # pragma: no cover - safety guard
                continue
            if exported:
                text = str(exported)
                break

    if not text:
        text = str(document)

    return text, {}


def _extract_docx_metadata(docx: zipfile.ZipFile) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    try:
        core = docx.read("docProps/core.xml")
    except KeyError:
        return metadata

    try:
        root = ET.fromstring(core)
    except ET.ParseError:
        return metadata

    ns = {
        "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    title_node = root.find("dc:title", ns)
    if title_node is not None and title_node.text:
        metadata["title"] = title_node.text.strip()

    creator_node = root.find("dc:creator", ns)
    if creator_node is not None and creator_node.text:
        metadata["authors"] = [creator_node.text.strip()]

    return metadata


def _fallback_docx_text(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as handle:
            try:
                xml_bytes = handle.read("word/document.xml")
            except KeyError:
                return read_text_file(path), {}

            try:
                root = ET.fromstring(xml_bytes)
            except ET.ParseError:
                return read_text_file(path), {}

            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paragraphs: list[str] = []
            for paragraph in root.findall(".//w:p", ns):
                texts = [
                    node.text for node in paragraph.findall(".//w:t", ns) if node.text
                ]
                if texts:
                    paragraphs.append("".join(texts))

            metadata = _extract_docx_metadata(handle)
            text_content = "\n\n".join(paragraphs).strip()
            return text_content, metadata
    except zipfile.BadZipFile:
        pass
    except OSError:
        pass

    return read_text_file(path), {}


def parse_docx_document(path: Path, *, max_tokens: int) -> ParserResult:
    from .chunking import chunk_text

    docling_payload = _docling_extract_text(path)
    if docling_payload:
        text, metadata = docling_payload
        parser = "docling"
        parser_version = _package_version("docling", "2.x")
    else:
        text, metadata = _fallback_docx_text(path)
        parser = "docx_fallback"
        parser_version = "0.1.0"

    chunks = chunk_text(text, max_tokens=max_tokens)
    return ParserResult(
        text=text,
        chunks=chunks,
        parser=parser,
        parser_version=parser_version,
        metadata=metadata,
    )


class _HTMLExtractor(HTMLParser):
    _BLOCK_TAGS = {
        "article",
        "div",
        "section",
        "p",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "br",
    }

    _SKIP_TAGS = {"script", "style", "noscript", "template"}

    def __init__(self) -> None:
        super().__init__()
        self._current_title = False
        self._title_chunks: list[str] = []
        self._body_chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs):  # type: ignore[override]
        lower = tag.lower()
        if lower == "title":
            self._current_title = True
        if lower in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if lower == "br":
            self._body_chunks.append("\n")
        elif lower in self._BLOCK_TAGS:
            self._body_chunks.append("\n")

    def handle_endtag(self, tag: str):  # type: ignore[override]
        lower = tag.lower()
        if lower == "title":
            self._current_title = False
        if lower in self._SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if lower in self._BLOCK_TAGS and lower != "br":
            self._body_chunks.append("\n")

    def handle_data(self, data: str):  # type: ignore[override]
        if self._skip_depth:
            return
        stripped = data.strip()
        if not stripped:
            return
        if self._current_title:
            self._title_chunks.append(stripped)
        self._body_chunks.append(stripped)

    def result(self) -> tuple[str, dict[str, Any]]:
        text = re.sub(r"\s+", " ", " ".join(self._body_chunks)).strip()
        metadata: dict[str, Any] = {}
        if self._title_chunks:
            metadata["title"] = " ".join(self._title_chunks)
        return text, metadata


def _parse_html_with_unstructured(
    path: Path, raw_html: str | None = None
) -> tuple[str, dict[str, Any]] | None:
    try:
        from unstructured.partition.html import partition_html
    except Exception:  # pragma: no cover - optional dependency
        return None

    if raw_html is not None:
        html_text = raw_html
    else:
        try:
            # Decode the HTML upfront so we can fall back to replacement characters when
            # encountering unexpected encodings (for example Windows-1252 smart quotes).
            # Passing the decoded text into ``partition_html`` avoids the library trying
            # to re-open the file using a strict UTF-8 decode, which previously caused
            # guardrail tests to miss lossy substitutions that our pipeline expects.
            html_text = read_text_file(path)
        except OSError:
            return None

    try:
        elements = partition_html(text=html_text, metadata_filename=path.name)

    except Exception:  # pragma: no cover - runtime guard
        return None

    text_chunks: list[str] = []
    metadata: dict[str, Any] = {}
    for element in elements:
        text = getattr(element, "text", None)
        if isinstance(text, str) and text.strip():
            text_chunks.append(text.strip())
        meta = getattr(element, "metadata", None)
        title = getattr(meta, "title", None) if meta else None
        if title and "title" not in metadata:
            metadata["title"] = title

    combined = "\n\n".join(text_chunks).strip()
    return combined, metadata


def parse_html_document(path: Path, *, max_tokens: int) -> ParserResult:
    from .chunking import chunk_text

    try:
        raw_html = read_text_file(path)
    except OSError as exc:
        from .exceptions import UnsupportedSourceError

        raise UnsupportedSourceError(
            f"Unable to read HTML document '{path.name}'"
        ) from exc

    parse_callable = _parse_html_with_unstructured
    parsed: tuple[str, dict[str, Any]] | None
    try:
        signature = inspect.signature(parse_callable)
    except (TypeError, ValueError):  # pragma: no cover - builtins or C extensions
        signature = None

    if signature is not None:
        parameters = list(signature.parameters.values())
        accepts_multiple_args = any(
            param.kind in {param.VAR_POSITIONAL, param.VAR_KEYWORD}
            for param in parameters
        ) or len(parameters) > 1
        if accepts_multiple_args:
            parsed = parse_callable(path, raw_html)
        else:
            parsed = parse_callable(path)
    else:  # pragma: no cover - fallback for dynamic callables
        try:
            parsed = parse_callable(path, raw_html)
        except TypeError:
            parsed = parse_callable(path)

    if parsed:
        text, metadata = parsed
        parser = "unstructured"
        parser_version = _package_version("unstructured", "0.15.x")
    else:
        extractor = _HTMLExtractor()
        try:
            extractor.feed(raw_html)
        except Exception:
            extractor = _HTMLExtractor()
            try:
                extractor.feed(raw_html)
            except Exception as inner_exc:  # pragma: no cover - defensive
                from .exceptions import UnsupportedSourceError

                raise UnsupportedSourceError(
                    f"Unable to parse HTML document '{path.name}'"
                ) from inner_exc

        text, metadata = extractor.result()
        parser = "html_fallback"
        parser_version = "0.1.0"

    chunks = chunk_text(text, max_tokens=max_tokens)
    return ParserResult(
        text=text,
        chunks=chunks,
        parser=parser,
        parser_version=parser_version,
        metadata=metadata,
    )


def parse_pdf_document(
    path: Path, *, max_pages: int | None, max_tokens: int
) -> ParserResult | _PdfExtractionErrorSentinel:
    from .chunking import chunk_text

    pages = parse_pdf(path, max_pages=max_pages)
    if pages is PDF_EXTRACTION_UNSUPPORTED:
        return PDF_EXTRACTION_UNSUPPORTED
    if not pages:
        return ParserResult(
            text="", chunks=[], parser="pdfminer", parser_version="0.2.0"
        )

    chunks: list["Chunk"] = []
    index = 0
    cursor = 0
    text_parts: list[str] = []
    for page in pages:
        text_parts.append(page.text)
        page_chunks = chunk_text(page.text, max_tokens=max_tokens)
        for chunk in page_chunks:
            chunk.page_no = page.page_no
            chunk.index = index
            chunk.start_char += cursor
            chunk.end_char += cursor
            chunks.append(chunk)
            index += 1
        cursor += len(page.text) + 1

    full_text = "\n".join(text_parts)
    return ParserResult(
        text=full_text, chunks=chunks, parser="pdfminer", parser_version="0.2.0"
    )


def parse_audio_document(
    path: Path,
    *,
    max_tokens: int,
    settings,
    frontmatter: dict[str, Any] | None,
) -> ParserResult:
    from .chunking import Chunk, chunk_text, chunk_transcript

    transcript_segments: list[TranscriptSegment] | None = None
    transcript_text: str | None = None
    metadata: dict[str, Any] = {}

    if frontmatter:
        maybe_segments = frontmatter.get("transcript_segments")
        if isinstance(maybe_segments, list):
            segments: list[TranscriptSegment] = []
            for item in maybe_segments:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                start = float(item.get("start", 0.0))
                end = float(item.get("end", start))
                speaker = item.get("speaker")
                segments.append(
                    TranscriptSegment(text=text, start=start, end=end, speaker=speaker)
                )
            if segments:
                transcript_segments = segments

        maybe_text = frontmatter.get("transcript")
        if isinstance(maybe_text, str) and maybe_text.strip():
            transcript_text = maybe_text.strip()

        transcript_path = frontmatter.get("transcript_path")
        if (
            isinstance(transcript_path, str)
            and not transcript_segments
            and not transcript_text
        ):
            candidate = Path(transcript_path)
            if not candidate.is_absolute():
                fixtures_root = getattr(settings, "fixtures_root", None)
                if fixtures_root:
                    candidate = Path(fixtures_root) / candidate
                else:
                    candidate = path.parent / candidate
            if candidate.exists():
                suffix = candidate.suffix.lower()
                if suffix in {".vtt", ".webvtt", ".srt", ".json"}:
                    transcript_segments = load_transcript(candidate)
                else:
                    transcript_text = read_text_file(candidate).strip()

    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate() or 1
                duration = frames / rate if rate else 0.0
                if duration:
                    metadata.setdefault("duration_seconds", int(duration))
        except wave.Error:
            pass
        except FileNotFoundError:  # pragma: no cover - defensive
            pass

    if transcript_segments:
        chunks = chunk_transcript(
            transcript_segments,
            max_tokens=max_tokens,
            max_window_seconds=getattr(settings, "transcript_max_window", 40.0),
        )
        text = " ".join(segment.text for segment in transcript_segments)
        return ParserResult(
            text=text,
            chunks=chunks,
            parser="transcript",
            parser_version="0.3.0",
            metadata=metadata,
        )

    if transcript_text:
        chunks = chunk_text(transcript_text, max_tokens=max_tokens)
        return ParserResult(
            text=transcript_text,
            chunks=chunks,
            parser="audio_transcript_text",
            parser_version="0.1.0",
            metadata=metadata,
        )

    placeholder = "Transcription pending for audio source."
    chunk = Chunk(
        text=placeholder,
        start_char=0,
        end_char=len(placeholder),
        index=0,
        t_start=0.0,
        t_end=0.0,
    )
    return ParserResult(
        text=placeholder,
        chunks=[chunk],
        parser="audio_pending",
        parser_version="0.1.0",
        metadata=metadata,
    )
