"""Utilities for detecting and formatting OSIS scripture references."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

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
