"""Persistence helpers for verse relationship graphs."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..ingest.osis import expand_osis_reference, osis_intersects
from .models import CommentaryExcerptSeed, ContradictionSeed, HarmonySeed

_ALLOWED_PERSPECTIVES = {"apologetic", "skeptical", "neutral"}


def _normalize_perspective(raw: str | None, *, default: str) -> str:
    value = (raw or default).strip().lower()
    if value not in _ALLOWED_PERSPECTIVES:
        return default
    return value


def _normalize_tags(tags: list[str] | None) -> list[str] | None:
    if not tags:
        return None
    normalised: list[str] = []
    for tag in tags:
        if not tag:
            continue
        normalised.append(str(tag))
    return normalised or None


def _osis_matches(candidate: str, requested: str) -> bool:
    return bool(
        osis_intersects(candidate, requested) or osis_intersects(requested, candidate)
    )


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

    target_ids = expand_osis_reference(osis)
    target_start = min(target_ids) if target_ids else None
    target_end = max(target_ids) if target_ids else None

    contradictions: list[PairSeedRecord] = []
    contradiction_query = session.query(ContradictionSeed)
    if target_start is not None and target_end is not None:
        range_predicate = or_(
            and_(
                ContradictionSeed.start_verse_id_a <= target_end,
                ContradictionSeed.end_verse_id_a >= target_start,
            ),
            and_(
                ContradictionSeed.start_verse_id_b <= target_end,
                ContradictionSeed.end_verse_id_b >= target_start,
            ),
        )
        contradiction_query = contradiction_query.filter(range_predicate)
    for seed in contradiction_query.all():
        if not (_osis_matches(seed.osis_a, osis) or _osis_matches(seed.osis_b, osis)):
            continue
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
    harmony_query = session.query(HarmonySeed)
    if target_start is not None and target_end is not None:
        harmony_query = harmony_query.filter(
            or_(
                and_(
                    HarmonySeed.start_verse_id_a <= target_end,
                    HarmonySeed.end_verse_id_a >= target_start,
                ),
                and_(
                    HarmonySeed.start_verse_id_b <= target_end,
                    HarmonySeed.end_verse_id_b >= target_start,
                ),
            )
        )
    for seed in harmony_query.all():
        if not (_osis_matches(seed.osis_a, osis) or _osis_matches(seed.osis_b, osis)):
            continue
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
    commentary_query = session.query(CommentaryExcerptSeed)
    if target_start is not None and target_end is not None:
        commentary_query = commentary_query.filter(
            and_(
                CommentaryExcerptSeed.start_verse_id <= target_end,
                CommentaryExcerptSeed.end_verse_id >= target_start,
            )
        )
    for seed in commentary_query.all():
        if not _osis_matches(seed.osis, osis):
            continue
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
