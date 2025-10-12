"""TEI-aware ingestion pipeline for scanned corpora."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Iterable, Protocol
import xml.etree.ElementTree as ET

from sqlalchemy.orm import Session

from theo.application.facades.settings import get_settings
from ..db.models import Document, Passage
from .chunking import Chunk, chunk_text
from .embeddings import get_embedding_service, lexical_representation
from .sanitizer import sanitize_passage_text
from .osis import detect_osis_references
from ..telemetry import instrument_workflow, set_span_attribute


@dataclass(slots=True)
class HTRResult:
    """Output from an OCR/HTR client."""

    text: str
    confidence: float
    page_no: int | None = None


class HTRClientProtocol(Protocol):
    """Protocol describing the subset of the Transkribus client we rely on."""

    def transcribe(self, path: Path) -> Iterable[HTRResult]:
        """Return recognised text with per-page confidence scores."""

        ...


_KNOWN_PLACES = {
    "Alexandria",
    "Antioch",
    "Carthage",
    "Constantinople",
    "Jerusalem",
    "Rome",
}


_PERSON_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")


def _normalise_confidence(confidences: Iterable[float]) -> float:
    values = [value for value in confidences if value is not None]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _extract_facets(text: str) -> tuple[list[str], list[str]]:
    persons: set[str] = set()
    places: set[str] = set()
    for match in _PERSON_PATTERN.finditer(text):
        candidate = match.group(1).strip()
        if not candidate:
            continue
        if candidate in _KNOWN_PLACES:
            places.add(candidate)
            continue
        if candidate.lower() in {"scripture", "chapter"}:
            continue
        if len(candidate) < 3:
            continue
        persons.add(candidate)
    return sorted(persons), sorted(places)


def _build_speaker_segments(text: str) -> list[tuple[str | None, str]]:
    segments: list[tuple[str | None, str]] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if ":" in stripped:
            speaker, content = stripped.split(":", 1)
            speaker_name = speaker.strip()
            if speaker_name:
                segments.append((speaker_name, content.strip()))
                continue
        segments.append((None, stripped))
    return segments


def _tei_element(tag: str, text: str | None = None, **attrib) -> ET.Element:
    element = ET.Element(tag, attrib)
    if text:
        element.text = text
    return element


def generate_tei_markup(text: str) -> tuple[str, dict[str, list[str]]]:
    """Create minimal TEI markup and structured facets for *text*."""

    tei = ET.Element("TEI", xmlns="http://www.tei-c.org/ns/1.0")
    tei_header = _tei_element("teiHeader")
    file_desc = _tei_element("fileDesc")
    title_stmt = _tei_element("titleStmt")
    title_stmt.append(_tei_element("title", "Theo Engine transcription"))
    file_desc.append(title_stmt)
    tei_header.append(file_desc)
    tei.append(tei_header)

    text_el = _tei_element("text")
    body = _tei_element("body")

    persons, places = _extract_facets(text)
    scripture = detect_osis_references(text)

    if persons:
        list_person = _tei_element("listPerson")
        for person in persons:
            list_person.append(_tei_element("person", None, n=person))
        body.append(list_person)

    if places:
        list_place = _tei_element("listPlace")
        for place in places:
            list_place.append(_tei_element("place", None, n=place))
        body.append(list_place)

    for speaker, segment_text in _build_speaker_segments(text):
        paragraph = _tei_element("p", segment_text)
        if scripture.all:
            for reference in scripture.all:
                ref_el = _tei_element("ref", reference, type="scripture", target=reference)
                paragraph.append(ref_el)
        if speaker:
            sp = _tei_element("sp", who=f"#{speaker.replace(' ', '_')}" )
            sp.append(_tei_element("speaker", speaker))
            sp.append(paragraph)
            body.append(sp)
        else:
            body.append(paragraph)

    text_el.append(body)
    tei.append(text_el)

    facets = {
        "persons": persons,
        "places": places,
        "scripture": scripture.all,
    }

    tei_xml = ET.tostring(tei, encoding="unicode")
    return tei_xml, facets


def _chunk_to_passage_meta(chunk: Chunk, facets: dict[str, list[str]], confidence: float) -> dict:
    detected = detect_osis_references(chunk.text)
    facets_with_scripture = {
        **facets,
        "scripture": detected.all,
    }
    search_terms = sorted({term for values in facets_with_scripture.values() for term in values})
    meta: dict[str, object] = {
        "ocr_confidence": confidence,
        "tei": facets_with_scripture,
    }
    if search_terms:
        meta["tei_search_blob"] = " ".join(search_terms)
    if detected.primary:
        meta["osis_primary"] = detected.primary
    if detected.all:
        meta["osis_refs_all"] = detected.all
    if chunk.speakers:
        meta["speakers"] = chunk.speakers
    return meta


def ingest_pilot_corpus(
    session: Session,
    corpus_path: Path,
    *,
    htr_client: HTRClientProtocol,
    document_metadata: dict[str, object] | None = None,
) -> Document:
    """Ingest a pilot corpus using an OCR/HTR client and emit TEI-aware passages."""

    with instrument_workflow(
        "ingest.tei", corpus_path=str(corpus_path)
    ) as span:
        path = Path(corpus_path)
        if path.is_dir():
            inputs = sorted(p for p in path.iterdir() if p.is_file())
        else:
            inputs = [path]

        texts: list[str] = []
        confidences: list[float] = []
        page_numbers: list[int | None] = []
        for input_path in inputs:
            for result in htr_client.transcribe(input_path):
                cleaned = result.text.strip()
                if not cleaned:
                    continue
                texts.append(cleaned)
                confidences.append(result.confidence)
                page_numbers.append(result.page_no)

        combined_text = "\n\n".join(texts)

        title = None
        authors = None
        collection = None
        if document_metadata:
            title = str(document_metadata.get("title") or "") or path.stem
            raw_authors = document_metadata.get("authors")
            if isinstance(raw_authors, str):
                authors = [raw_authors]
            elif isinstance(raw_authors, Iterable):
                authors = [str(author) for author in raw_authors]
            collection = document_metadata.get("collection")
        if not title:
            title = path.stem

        document = Document(
            title=title,
            authors=authors,
            collection=str(collection) if collection else None,
            source_type="tei_pipeline",
        )
        session.add(document)
        session.flush()

        chunks = chunk_text(combined_text)
        chunk_count = len(chunks)
        set_span_attribute(span, "ingest.source_type", "tei_pipeline")
        set_span_attribute(span, "ingest.chunk_count", chunk_count)
        set_span_attribute(span, "ingest.batch_size", min(chunk_count, 32))
        set_span_attribute(span, "ingest.cache_status", "n/a")

        embedding_service = get_embedding_service()
        sanitized_texts = [sanitize_passage_text(chunk.text) for chunk in chunks]
        embeddings = embedding_service.embed(sanitized_texts)
        average_confidence = _normalise_confidence(confidences) or 0.0

        for index, chunk in enumerate(chunks):
            tei_xml, facets = generate_tei_markup(chunk.text)
            meta = _chunk_to_passage_meta(chunk, facets, average_confidence)
            page_no = page_numbers[index] if index < len(page_numbers) else None
            sanitized_text = (
                sanitized_texts[index]
                if index < len(sanitized_texts)
                else sanitize_passage_text(chunk.text)
            )
            passage = Passage(
                document_id=document.id,
                page_no=page_no,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                text=sanitized_text,
                raw_text=chunk.text,
                tokens=len(sanitized_text.split()),
                osis_ref=meta.get("osis_primary"),
                embedding=embeddings[index] if index < len(embeddings) else None,
                lexeme=lexical_representation(session, sanitized_text),
                meta=meta,
                tei_xml=tei_xml,
            )
            session.add(passage)

        session.flush()

        settings = get_settings()
        document.provenance_score = getattr(settings, "tei_pipeline_provenance", 80)
        set_span_attribute(span, "ingest.document_id", document.id)
        return document

