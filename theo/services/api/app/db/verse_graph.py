"""Persistence helpers for verse relationship graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, TypeVar

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from theo.services.api.app.persistence_models import (
    CommentaryExcerptSeed,
    ContradictionSeed,
    HarmonySeed,
)
from ..ingest.osis import expand_osis_reference, osis_intersects

_ALLOWED_PERSPECTIVES = {"apologetic", "skeptical", "neutral"}


@dataclass(frozen=True, slots=True)
class VerseWindow:
    """Normalized verse slice used for range checks."""

    reference: str
    start: int
    end: int
    verse_ids: frozenset[int]

    def intersects(self, candidate: frozenset[int]) -> bool:
        if not candidate:
            return False
        candidate_start = min(candidate)
        candidate_end = max(candidate)
        if candidate_end < self.start or candidate_start > self.end:
            return False
        return not self.verse_ids.isdisjoint(candidate)


def _normalize_perspective(raw: str | None, *, default: str) -> str:
    value = (raw or default).strip().lower()
    if value not in _ALLOWED_PERSPECTIVES:
        return default
    return value


PairSeedModel = TypeVar("PairSeedModel", ContradictionSeed, HarmonySeed)


def _normalize_tags(tags: list[str] | None) -> list[str] | None:
    if not tags:
        return None
    normalised: list[str] = []
    for tag in tags:
        if not tag:
            continue
        normalised.append(str(tag))
    return normalised or None


def compute_verse_id_ranges(references: Iterable[str]) -> dict[str, VerseWindow]:
    """Return a mapping of normalized OSIS references to verse windows."""

    ranges: dict[str, VerseWindow] = {}
    for value in references:
        if not value:
            continue
        normalized = value.strip()
        if not normalized or normalized in ranges:
            continue
        verse_ids = expand_osis_reference(normalized)
        if not verse_ids:
            continue
        start = min(verse_ids)
        end = max(verse_ids)
        ranges[normalized] = VerseWindow(
            reference=normalized,
            start=start,
            end=end,
            verse_ids=verse_ids,
        )
    return ranges


def _merge_numeric_windows(windows: Iterable[VerseWindow]) -> list[tuple[int, int]]:
    """Coalesce overlapping numeric windows for SQL filtering."""

    intervals = sorted((window.start, window.end) for window in windows)
    merged: list[list[int]] = []
    for start, end in intervals:
        if not merged:
            merged.append([start, end])
            continue
        last = merged[-1]
        if start <= last[1] + 1:
            if end > last[1]:
                last[1] = end
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _range_condition(start_column: Any, end_column: Any, start: int, end: int) -> Any:
    if start_column is None or end_column is None:
        return None
    return and_(
        start_column.isnot(None),
        end_column.isnot(None),
        start_column <= end,
        end_column >= start,
    )


def _reference_intersects(
    reference: str | None,
    windows: list[VerseWindow],
    cache: dict[str, frozenset[int]],
) -> bool:
    if not reference:
        return False
    normalized = reference.strip()
    if not normalized:
        return False
    if normalized not in cache:
        cache[normalized] = expand_osis_reference(normalized)
    candidate = cache[normalized]
    if not candidate:
        return False
    return any(window.intersects(candidate) for window in windows)


def query_pair_seed_rows(
    session: Session,
    verse_windows: Iterable[VerseWindow],
    model: type[PairSeedModel],
) -> list[PairSeedModel]:
    """Return ORM rows for pairwise seeds overlapping ``verse_windows``."""

    windows = list(verse_windows)
    if not windows:
        return []

    range_pairs: list[tuple[Any, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for start_attr, end_attr in (
        ("start_verse_id_a", "end_verse_id_a"),
        ("start_verse_id", "end_verse_id"),
        ("start_verse_id_b", "end_verse_id_b"),
    ):
        start_column = getattr(model, start_attr, None)
        end_column = getattr(model, end_attr, None)
        if start_column is None or end_column is None:
            continue
        pair_key = (
            getattr(start_column, "key", start_attr),
            getattr(end_column, "key", end_attr),
        )
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        range_pairs.append((start_column, end_column))

    window_conditions = []
    for start, end in _merge_numeric_windows(windows):
        per_window = [
            condition
            for start_column, end_column in range_pairs
            if (condition := _range_condition(start_column, end_column, start, end))
            is not None
        ]
        if per_window:
            window_conditions.append(or_(*per_window))

    if not window_conditions:
        return []

    query = session.query(model).filter(or_(*window_conditions))
    seen: dict[str, PairSeedModel] = {}
    cache: dict[str, frozenset[int]] = {}
    for seed in query:
        intersects_a = _reference_intersects(
            getattr(seed, "osis_a", None), windows, cache
        )
        intersects_b = _reference_intersects(
            getattr(seed, "osis_b", None), windows, cache
        )
        if intersects_a or intersects_b:
            seen[seed.id] = seed
    return list(seen.values())


def query_commentary_seed_rows(
    session: Session, verse_windows: Iterable[VerseWindow]
) -> list[CommentaryExcerptSeed]:
    """Return commentary seeds overlapping ``verse_windows``."""

    conditions = []
    start_column = getattr(CommentaryExcerptSeed, "start_verse_id", None)
    end_column = getattr(CommentaryExcerptSeed, "end_verse_id", None)
    if start_column is None or end_column is None:
        return []

    windows = list(verse_windows)
    if not windows:
        return []

    for start, end in _merge_numeric_windows(windows):
        condition = _range_condition(start_column, end_column, start, end)
        if condition is not None:
            conditions.append(condition)

    if not conditions:
        return []

    query = session.query(CommentaryExcerptSeed).filter(or_(*conditions))
    seen: dict[str, CommentaryExcerptSeed] = {}
    cache: dict[str, frozenset[int]] = {}
    for seed in query:
        if _reference_intersects(seed.osis, windows, cache):
            seen[seed.id] = seed
    return list(seen.values())


@dataclass(slots=True)
class PairSeedRecord:
    """Normalized representation of a two-verse seed relationship."""

    id: str
    osis_a: str
    osis_b: str
    summary: str | None
    source: str | None
    tags: list[str] | None
    weight: float | None
    perspective: str


@dataclass(slots=True)
class CommentarySeedRecord:
    """Normalized representation of a commentary excerpt seed."""

    id: str
    osis: str
    title: str | None
    excerpt: str
    source: str | None
    tags: list[str] | None
    perspective: str


@dataclass(slots=True)
class VerseSeedRelationships:
    """Container for graph seed data associated with a verse."""

    contradictions: list[PairSeedRecord]
    harmonies: list[PairSeedRecord]
    commentaries: list[CommentarySeedRecord]


def load_seed_relationships(session: Session, osis: str) -> VerseSeedRelationships:
    """Return normalized seed records intersecting ``osis``."""

    windows = list(compute_verse_id_ranges([osis]).values())

    contradictions: list[PairSeedRecord] = []
    for seed in query_pair_seed_rows(session, windows, ContradictionSeed):
        perspective = _normalize_perspective(seed.perspective, default="skeptical")
        contradictions.append(
            PairSeedRecord(
                id=seed.id,
                osis_a=seed.osis_a,
                osis_b=seed.osis_b,
                summary=seed.summary,
                source=seed.source,
                tags=_normalize_tags(seed.tags),
                weight=float(seed.weight) if seed.weight is not None else None,
                perspective=perspective,
            )
        )

    harmonies: list[PairSeedRecord] = []
    for seed in query_pair_seed_rows(session, windows, HarmonySeed):
        perspective = _normalize_perspective(seed.perspective, default="apologetic")
        harmonies.append(
            PairSeedRecord(
                id=seed.id,
                osis_a=seed.osis_a,
                osis_b=seed.osis_b,
                summary=seed.summary,
                source=seed.source,
                tags=_normalize_tags(seed.tags),
                weight=float(seed.weight) if seed.weight is not None else None,
                perspective=perspective,
            )
        )

    commentaries: list[CommentarySeedRecord] = []
    for seed in query_commentary_seed_rows(session, windows):
        perspective = _normalize_perspective(seed.perspective, default="neutral")
        commentaries.append(
            CommentarySeedRecord(
                id=seed.id,
                osis=seed.osis,
                title=seed.title,
                excerpt=seed.excerpt,
                source=seed.source,
                tags=_normalize_tags(seed.tags),
                perspective=perspective,
            )
        )

    return VerseSeedRelationships(
        contradictions=contradictions,
        harmonies=harmonies,
        commentaries=commentaries,
    )
