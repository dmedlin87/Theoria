"""Service helpers for contradiction discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..db.models import ContradictionSeed, HarmonySeed
from ..ingest.osis import expand_osis_reference, osis_intersects
from ..models.research import ContradictionItem

PERSPECTIVE_CHOICES: tuple[str, ...] = ("apologetic", "skeptical", "neutral")

_CONTRADICTION_PERSPECTIVES = {"skeptical", "neutral"}
_HARMONY_PERSPECTIVES = {"apologetic", "neutral"}


@dataclass(slots=True)
class _ScoredSeed:
    seed: ContradictionSeed | HarmonySeed
    score: float
    perspective: str


def _normalize_osis(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if not value:
            continue
        normalized.append(value.strip())
    return normalized


def _normalize_perspective(raw: str | None, *, default: str) -> str:
    value = (raw or default).strip().lower()
    if value not in PERSPECTIVE_CHOICES:
        return default
    return value


def search_contradictions(
    session: Session,
    *,
    osis: str | list[str],
    topic: str | None = None,
    perspectives: list[str] | None = None,
    limit: int = 25,
) -> list[ContradictionItem]:
    """Return ranked contradiction entries intersecting the provided OSIS."""

    candidates = _normalize_osis([osis] if isinstance(osis, str) else osis)
    if not candidates:
        return []

    allowed_perspectives = {
        p.strip().lower()
        for p in (perspectives or [])
        if p and p.strip().lower() in PERSPECTIVE_CHOICES
    }
    if not allowed_perspectives and perspectives:
        # If filters were provided but none are valid, return empty set.
        return []

    candidate_ranges: list[tuple[str, int, int]] = []
    for requested in candidates:
        verse_ids = expand_osis_reference(requested)
        if not verse_ids:
            continue
        candidate_ranges.append((requested, min(verse_ids), max(verse_ids)))
    if not candidate_ranges:
        return []

    topic_lower = topic.lower() if topic else None
    scored: list[_ScoredSeed] = []

    def _should_include(tags: list[str] | None) -> bool:
        if not topic_lower:
            return True
        tag_values = tags or []
        return any(tag.lower() == topic_lower for tag in tag_values)

    def _allowed_perspective(value: str) -> bool:
        if not allowed_perspectives:
            return True
        return value in allowed_perspectives

    def _range_predicate(model: type[ContradictionSeed] | type[HarmonySeed]):
        clauses = []
        for _, start, end in candidate_ranges:
            clauses.append(
                and_(model.start_verse_id_a <= end, model.end_verse_id_a >= start)
            )
            clauses.append(
                and_(model.start_verse_id_b <= end, model.end_verse_id_b >= start)
            )
        return or_(*clauses) if clauses else None

    contradiction_query = session.query(ContradictionSeed)
    harmony_query = session.query(HarmonySeed)

    if allowed_perspectives:
        contradiction_values = list(allowed_perspectives & _CONTRADICTION_PERSPECTIVES)
        if contradiction_values:
            contradiction_query = contradiction_query.filter(
                ContradictionSeed.perspective.in_(contradiction_values)
            )
        else:
            contradiction_query = None

        harmony_values = list(allowed_perspectives & _HARMONY_PERSPECTIVES)
        if harmony_values:
            harmony_query = harmony_query.filter(
                HarmonySeed.perspective.in_(harmony_values)
            )
        else:
            harmony_query = None

    if contradiction_query is not None:
        predicate = _range_predicate(ContradictionSeed)
        if predicate is not None:
            contradiction_query = contradiction_query.filter(predicate)
        contradiction_seeds = contradiction_query.all()
    else:
        contradiction_seeds = []

    if harmony_query is not None:
        predicate = _range_predicate(HarmonySeed)
        if predicate is not None:
            harmony_query = harmony_query.filter(predicate)
        harmony_seeds = harmony_query.all()
    else:
        harmony_seeds = []

    for seed in contradiction_seeds:
        perspective = _normalize_perspective(seed.perspective, default="skeptical")
        if not _allowed_perspective(perspective):
            continue
        if not _should_include(seed.tags):
            continue

        intersects = any(
            osis_intersects(seed.osis_a, requested)
            or osis_intersects(seed.osis_b, requested)
            for requested in candidates
        )
        if not intersects:
            continue

        score = float(seed.weight or 0.0)
        scored.append(_ScoredSeed(seed=seed, score=score, perspective=perspective))

    for seed in harmony_seeds:
        perspective = _normalize_perspective(seed.perspective, default="apologetic")
        if not _allowed_perspective(perspective):
            continue
        if not _should_include(seed.tags):
            continue

        intersects = any(
            osis_intersects(seed.osis_a, requested)
            or osis_intersects(seed.osis_b, requested)
            for requested in candidates
        )
        if not intersects:
            continue

        score = float(seed.weight or 0.0)
        scored.append(_ScoredSeed(seed=seed, score=score, perspective=perspective))

    scored.sort(
        key=lambda entry: (
            -entry.score,
            entry.perspective,
            entry.seed.summary or "",
            entry.seed.id,
        )
    )

    items: list[ContradictionItem] = []
    for entry in scored[:limit]:
        seed = entry.seed
        items.append(
            ContradictionItem(
                id=seed.id,
                osis_a=seed.osis_a,
                osis_b=seed.osis_b,
                summary=seed.summary,
                source=seed.source,
                tags=list(seed.tags) if seed.tags else None,
                weight=float(seed.weight or 0.0),
                perspective=entry.perspective,
            )
        )

    return items
