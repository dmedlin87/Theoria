"""Utilities for detecting, normalising, and parsing OSIS content."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

try:  # pragma: no cover - exercised via regression tests when optional dep present
    from defusedxml import ElementTree as ET
    from defusedxml.common import DefusedXmlException
except ModuleNotFoundError:  # pragma: no cover - fallback when ``defusedxml`` missing
    import types
    import xml.etree.ElementTree as _ET

    class DefusedXmlException(RuntimeError):
        """Raised when XML input contains disallowed constructs."""

    def _ensure_safe_xml(payload: Any) -> None:
        if isinstance(payload, (bytes, bytearray)):
            haystack_bytes = bytes(payload).upper()
            if b"<!DOCTYPE" in haystack_bytes or b"<!ENTITY" in haystack_bytes:
                raise DefusedXmlException("Unsafe XML constructs are not supported")
            return

        haystack = str(payload).upper()
        if "<!DOCTYPE" in haystack or "<!ENTITY" in haystack:
            raise DefusedXmlException("Unsafe XML constructs are not supported")

    def _secure_fromstring(text: Any, parser: Any | None = None):
        _ensure_safe_xml(text)
        if parser is None:
            parser = _ET.XMLParser(resolve_entities=False)
        return _ET.fromstring(text, parser=parser)

    ET = types.SimpleNamespace(  # type: ignore[assignment]
        ParseError=_ET.ParseError,
        fromstring=_secure_fromstring,
    )

import pythonbible as pb
from pythonbible import NormalizedReference

from theo.domain.research.osis import (
    expand_osis_reference,
    format_osis,
    osis_to_readable,
)

__all__ = [
    "expand_osis_reference",
    "format_osis",
    "osis_to_readable",
    "DetectedOsis",
    "OsisVerse",
    "OsisCommentaryEntry",
    "OsisDocument",
    "ResolvedCommentaryAnchor",
    "parse_osis_document",
    "canonicalize_osis_id",
    "combine_references",
    "detect_osis_references",
    "canonical_verse_range",
    "osis_intersects",
    "classify_osis_matches",
]


@dataclass
class DetectedOsis:
    """Detected references for a block of text."""

    primary: str | None
    all: list[str]


@dataclass(slots=True)
class OsisVerse:
    """Normalised OSIS verse payload."""

    osis_id: str
    text: str


@dataclass(slots=True)
class OsisCommentaryEntry:
    """Commentary excerpt resolved from OSIS markup."""

    excerpt: str
    anchors: list[str]
    title: str | None = None
    note_id: str | None = None


@dataclass(slots=True)
class OsisDocument:
    """Structured representation of an OSIS/XML document."""

    work: str | None
    title: str | None
    verses: list[OsisVerse]
    commentaries: list[OsisCommentaryEntry]
    metadata: dict[str, Any]


@dataclass(slots=True)
class ResolvedCommentaryAnchor:
    """Commentary excerpt anchored to a canonical OSIS reference."""

    osis: str
    excerpt: str
    title: str | None = None
    perspective: str | None = None
    source: str | None = None
    tags: list[str] | None = None
    note_id: str | None = None


def _strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _iter_text(node, exclude: set[str] | None = None) -> Iterable[str]:
    tag = _strip_namespace(getattr(node, "tag", "")) if hasattr(node, "tag") else ""
    if exclude and tag in exclude:
        return
    text = getattr(node, "text", None)
    if text:
        yield text
    for child in getattr(node, "__iter__", lambda: [])():
        yield from _iter_text(child, exclude)
        tail = getattr(child, "tail", None)
        if tail:
            yield tail


def _coalesce_text(node, *, exclude: set[str] | None = None) -> str:
    parts = [segment.strip() for segment in _iter_text(node, exclude) if segment]
    return " ".join(segment for segment in parts if segment)


def _extract_title(node) -> str | None:
    for child in getattr(node, "__iter__", lambda: [])():
        if _strip_namespace(getattr(child, "tag", "")) == "title":
            value = _coalesce_text(child)
            if value:
                return value
    return None


def _split_osis_tokens(value: str | None) -> list[str]:
    if not value:
        return []
    tokens: list[str] = []
    for token in value.replace(";", " ").split():
        cleaned = token.strip()
        if not cleaned:
            continue
        tokens.append(cleaned)
    return tokens


def canonicalize_osis_id(raw: str | None) -> str | None:
    if not raw:
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    if "!" in candidate:
        candidate = candidate.split("!", 1)[0]
    if not candidate:
        return None
    try:
        verse_ids = expand_osis_reference(candidate)
    except Exception:  # pragma: no cover - guard malformed values
        return None
    if not verse_ids:
        return None
    return candidate


def _collect_commentary_anchors(node) -> list[str]:
    anchors: list[str] = []
    for attr in ("osisRef", "osisID", "target"):
        anchors.extend(_split_osis_tokens(getattr(node, "attrib", {}).get(attr)))
    for child in getattr(node, "__iter__", lambda: [])():
        tag = _strip_namespace(getattr(child, "tag", ""))
        if tag in {"ref", "reference"}:
            anchors.extend(_split_osis_tokens(child.attrib.get("osisRef")))
        anchors.extend(_collect_commentary_anchors(child))
    canonical: list[str] = []
    seen: set[str] = set()
    for anchor in anchors:
        normalized = canonicalize_osis_id(anchor)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        canonical.append(normalized)
    return canonical


def parse_osis_document(xml_text: str) -> OsisDocument:
    """Parse an OSIS/XML payload into verses and commentary excerpts."""

    try:
        root = ET.fromstring(xml_text)
    except (ET.ParseError, DefusedXmlException) as exc:  # pragma: no cover - defensive
        raise ValueError("Invalid OSIS/XML payload") from exc

    work: str | None = None
    title: str | None = None
    metadata: dict[str, Any] = {}

    for element in getattr(root, "iter", lambda: [])():
        if _strip_namespace(getattr(element, "tag", "")) == "osisText":
            work = element.attrib.get("osisIDWork") or element.attrib.get("osisRefWork")
            if element.attrib.get("xml:lang"):
                metadata.setdefault("language", element.attrib.get("xml:lang"))
            inner_title = _extract_title(element)
            if inner_title and not title:
                title = inner_title
            break

    if not title:
        for element in getattr(root, "iter", lambda: [])():
            if _strip_namespace(getattr(element, "tag", "")) == "title":
                candidate = _coalesce_text(element)
                if candidate:
                    title = candidate
                    break

    verse_map: dict[str, OsisVerse] = {}
    for element in getattr(root, "iter", lambda: [])():
        if _strip_namespace(getattr(element, "tag", "")) != "verse":
            continue
        verse_text = _coalesce_text(element)
        if not verse_text:
            continue
        tokens = _split_osis_tokens(element.attrib.get("osisID"))
        if not tokens:
            tokens = _split_osis_tokens(element.attrib.get("osisRef"))
        for token in tokens:
            canonical = canonicalize_osis_id(token)
            if not canonical or canonical in verse_map:
                continue
            verse_map[canonical] = OsisVerse(osis_id=canonical, text=verse_text)

    commentaries: list[OsisCommentaryEntry] = []
    for element in getattr(root, "iter", lambda: [])():
        tag = _strip_namespace(getattr(element, "tag", ""))
        type_attr = element.attrib.get("type", "").lower()
        if tag == "note" and "commentary" not in type_attr:
            continue
        if tag == "div" and type_attr and "commentary" not in type_attr:
            continue
        if tag not in {"note", "div", "p"}:
            continue
        anchors = _collect_commentary_anchors(element)
        if not anchors:
            continue
        excerpt = _coalesce_text(element, exclude={"title"})
        if not excerpt:
            continue
        commentaries.append(
            OsisCommentaryEntry(
                excerpt=excerpt,
                anchors=anchors,
                title=_extract_title(element),
                note_id=element.attrib.get("osisID"),
            )
        )

    return OsisDocument(
        work=work,
        title=title,
        verses=list(verse_map.values()),
        commentaries=commentaries,
        metadata=metadata,
    )


def combine_references(
    references: Sequence[NormalizedReference],
) -> NormalizedReference | None:
    """Return a minimal covering range for contiguous references in the same book."""

    if not references:
        return None

    first_book = references[0].book
    if not all(ref.book == first_book for ref in references):
        return references[0]

    verse_ids: list[int] = []
    for ref in references:
        verse_ids.extend(pb.convert_reference_to_verse_ids(ref))

    if not verse_ids:
        return references[0]

    verse_ids = sorted(set(verse_ids))

    # Only combine references that form one continuous range.
    for previous, current in zip(verse_ids, verse_ids[1:]):
        if current != previous + 1:
            return None
    start_ref = pb.convert_verse_ids_to_references([verse_ids[0]])[0]
    end_ref = pb.convert_verse_ids_to_references([verse_ids[-1]])[0]
    return NormalizedReference(
        book=first_book,
        start_chapter=start_ref.start_chapter,
        start_verse=start_ref.start_verse,
        end_chapter=end_ref.end_chapter,
        end_verse=end_ref.end_verse,
        end_book=None,
    )


def detect_osis_references(text: str) -> DetectedOsis:
    """Detect OSIS references in arbitrary text."""

    normalized = pb.get_references(text)
    if not normalized:
        return DetectedOsis(primary=None, all=[])

    all_refs = [format_osis(ref) for ref in normalized]
    primary_ref = combine_references(normalized)
    primary = format_osis(primary_ref) if primary_ref else all_refs[0]
    return DetectedOsis(primary=primary, all=all_refs)


def _osis_to_readable(reference: str) -> str:
    """Convert an OSIS string into a pythonbible-friendly textual form.

    Historically this helper lived in the ingest layer; keep the name (and guard)
    so older callers continue to function while delegating to the shared domain
    implementation.
    """

    try:
        return osis_to_readable(reference)
    except Exception:  # pragma: no cover - defensive: fall back to original text
        return reference


def canonical_verse_range(
    references: Sequence[str] | None,
) -> tuple[list[int] | None, int | None, int | None]:
    """Return canonical verse identifiers and range bounds for *references*."""

    if not references:
        return None, None, None

    verse_ids: set[int] = set()
    for reference in references:
        if not reference:
            continue
        try:
            verse_ids.update(expand_osis_reference(reference))
        except Exception:  # pragma: no cover - defensive guard for malformed refs
            continue

    if not verse_ids:
        return None, None, None

    sorted_ids = sorted(verse_ids)
    return sorted_ids, sorted_ids[0], sorted_ids[-1]


def osis_intersects(a: str, b: str) -> bool:
    """Determine if two OSIS ranges intersect (basic overlap check)."""

    ids_a = expand_osis_reference(a)
    ids_b = expand_osis_reference(b)
    if not ids_a or not ids_b:
        return False
    return not ids_a.isdisjoint(ids_b)


def classify_osis_matches(
    detected: Sequence[str], hints: Sequence[str]
) -> tuple[list[str], list[str]]:
    """Separate hint references into those intersecting detected ranges and the rest."""

    detected_clean = [ref for ref in detected if ref]
    matched: list[str] = []
    unmatched: list[str] = []

    for hint in hints:
        if not hint:
            continue
        if not detected_clean:
            unmatched.append(hint)
            continue
        try:
            intersects = any(osis_intersects(candidate, hint) for candidate in detected_clean)
        except Exception:  # pragma: no cover - intersection should never fail but be safe
            intersects = False
        if intersects:
            if hint not in matched:
                matched.append(hint)
        elif hint not in unmatched:
            unmatched.append(hint)

    return matched, unmatched
