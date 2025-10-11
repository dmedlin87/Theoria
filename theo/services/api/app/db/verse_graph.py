"""Persistence helpers for verse relationship graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, TypeVar

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..ingest.osis import expand_osis_reference
from .models import CommentaryExcerptSeed, ContradictionSeed, HarmonySeed

_ALLOWED_PERSPECTIVES = {"apologetic", "skeptical", "neutral"}


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


def compute_verse_id_ranges(references: Iterable[str]) -> dict[str, tuple[int, int]]:
    """Return a mapping of normalized OSIS references to verse-id ranges."""

    ranges: dict[str, tuple[int, int]] = {}
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
        ranges[normalized] = (start, end)
    return ranges


def _range_condition(start_column, end_column, target: tuple[int, int]):
    if start_column is None or end_column is None:
        return None
    start, end = target
    return and_(
        start_column.isnot(None),
        end_column.isnot(None),
        start_column <= end,
        end_column >= start,
    )


def query_pair_seed_rows(
    session: Session,
    verse_ranges: Iterable[tuple[int, int]],
    model: type[PairSeedModel],
) -> list[PairSeedModel]:
    """Return ORM rows for pairwise seeds overlapping ``verse_ranges``."""

    conditions = []
    for verse_range in verse_ranges:
        per_range: list = []
        per_range.append(
            _range_condition(getattr(model, "start_verse_id", None), getattr(model, "end_verse_id", None), verse_range)
        )
        per_range.append(
            _range_condition(
                getattr(model, "start_verse_id_b", None),
                getattr(model, "end_verse_id_b", None),
                verse_range,
            )
        )
        per_range = [condition for condition in per_range if condition is not None]
        if per_range:
            conditions.append(or_(*per_range))

    if not conditions:
        return []

    query = session.query(model).filter(or_(*conditions))
    seen: dict[str, PairSeedModel] = {}
    for seed in query:
        seen[seed.id] = seed
    return list(seen.values())


def query_commentary_seed_rows(
    session: Session, verse_ranges: Iterable[tuple[int, int]]
) -> list[CommentaryExcerptSeed]:
    """Return commentary seeds overlapping ``verse_ranges``."""

    conditions = []
    start_column = getattr(CommentaryExcerptSeed, "start_verse_id", None)
    end_column = getattr(CommentaryExcerptSeed, "end_verse_id", None)
    if start_column is None or end_column is None:
        return []

    for verse_range in verse_ranges:
        condition = _range_condition(start_column, end_column, verse_range)
        if condition is not None:
            conditions.append(condition)

    if not conditions:
        return []

    query = session.query(CommentaryExcerptSeed).filter(or_(*conditions))
    seen: dict[str, CommentaryExcerptSeed] = {}
    for seed in query:
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

    ranges = list(compute_verse_id_ranges([osis]).values())

    contradictions: list[PairSeedRecord] = []
    for seed in query_pair_seed_rows(session, ranges, ContradictionSeed):
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
    for seed in query_pair_seed_rows(session, ranges, HarmonySeed):
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
    for seed in query_commentary_seed_rows(session, ranges):
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
