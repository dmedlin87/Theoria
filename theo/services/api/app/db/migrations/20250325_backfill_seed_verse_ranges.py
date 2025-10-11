"""Populate verse range metadata for seed tables."""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable

from sqlalchemy.orm import Session

from theo.services.api.app.ingest.osis import expand_osis_reference
from theo.services.api.app.db.models import (
    CommentaryExcerptSeed,
    ContradictionSeed,
    HarmonySeed,
)


@lru_cache(maxsize=512)
def _expanded(reference: str | None) -> frozenset[int]:
    if not reference:
        return frozenset()
    return expand_osis_reference(reference)


def _compute_range(reference: str | None) -> tuple[int, int] | None:
    verse_ids = _expanded(reference)
    if not verse_ids:
        return None
    return min(verse_ids), max(verse_ids)


def _update_pair_seed(seed, references: Iterable[tuple[str | None, str, str]]) -> bool:
    changed = False
    for reference, start_attr, end_attr in references:
        verse_range = _compute_range(reference)
        start_value = verse_range[0] if verse_range else None
        end_value = verse_range[1] if verse_range else None
        if getattr(seed, start_attr) != start_value:
            setattr(seed, start_attr, start_value)
            changed = True
        if getattr(seed, end_attr) != end_value:
            setattr(seed, end_attr, end_value)
            changed = True
    return changed


def apply(session: Session) -> None:
    """Backfill verse range metadata for seed tables."""

    updated = False

    for seed in session.query(ContradictionSeed):
        if _update_pair_seed(
            seed,
            (
                (seed.osis_a, "start_verse_id", "end_verse_id"),
                (seed.osis_b, "start_verse_id_b", "end_verse_id_b"),
            ),
        ):
            updated = True

    for seed in session.query(HarmonySeed):
        if _update_pair_seed(
            seed,
            (
                (seed.osis_a, "start_verse_id", "end_verse_id"),
                (seed.osis_b, "start_verse_id_b", "end_verse_id_b"),
            ),
        ):
            updated = True

    for seed in session.query(CommentaryExcerptSeed):
        verse_range = _compute_range(seed.osis)
        start_value = verse_range[0] if verse_range else None
        end_value = verse_range[1] if verse_range else None
        if seed.start_verse_id != start_value:
            seed.start_verse_id = start_value
            updated = True
        if seed.end_verse_id != end_value:
            seed.end_verse_id = end_value
            updated = True

    if updated:
        session.flush()
