"""Utilities to normalize OSIS references for evidence artifacts."""

from __future__ import annotations

from collections.abc import Iterable

import pythonbible as pb

from theo.domain.research.osis import format_osis, osis_to_readable


def normalize_reference(reference: str) -> tuple[str, ...]:
    """Normalize a single OSIS reference to canonical form(s)."""

    if not reference:
        return ()
    try:
        normalized = pb.get_references(osis_to_readable(reference))
    except Exception:  # pragma: no cover - defensive fallback for pythonbible
        return (reference,)
    if not normalized:
        return (reference,)
    return tuple(format_osis(ref) for ref in normalized)


def normalize_many(references: Iterable[str]) -> tuple[str, ...]:
    """Return a stable, deduplicated tuple of normalized OSIS references."""

    values: set[str] = set()
    for reference in references:
        values.update(normalize_reference(reference))
    if not values:
        return ()
    return tuple(sorted(values))


__all__ = ["normalize_reference", "normalize_many"]
