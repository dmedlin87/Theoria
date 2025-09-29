"""Service helpers for contradiction discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from ..db.models import ContradictionSeed, HarmonySeed
from ..ingest.osis import osis_intersects
from ..models.research import ContradictionItem


@dataclass(slots=True)
class _ScoredSeed:
    seed: ContradictionSeed
    score: float
    perspective: str


def _normalize_osis(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if not value:
            continue
        normalized.append(value.strip())
    return normalized


def _normalize_perspectives(values: str | Iterable[str] | None) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, str):
        iterable: Iterable[str] = [values]
    else:
        iterable = values
    normalized: set[str] = set()
    for value in iterable:
        if not value:
            continue
        normalized.add(str(value).strip().lower())
    return normalized


def _seed_perspective(value: str | None, *, fallback: str) -> str:
    normalized = (value or "").strip().lower()
    return normalized or fallback


def search_contradictions(
    session: Session,
    *,
    osis: str | list[str],
    topic: str | None = None,
    perspective: str | list[str] | None = None,
    limit: int = 25,
) -> list[ContradictionItem]:
    """Return ranked contradiction entries intersecting the provided OSIS."""

    candidates = _normalize_osis([osis] if isinstance(osis, str) else osis)
    if not candidates:
        return []

    requested_perspectives = _normalize_perspectives(perspective)
    include_all = not requested_perspectives
    contradiction_seeds = session.query(ContradictionSeed).all()
    harmony_seeds = session.query(HarmonySeed).all()
    topic_lower = topic.lower() if topic else None
    scored: list[_ScoredSeed] = []

    def _consider(seed: ContradictionSeed | HarmonySeed, *, fallback: str) -> None:
        label = _seed_perspective(getattr(seed, "perspective", None), fallback=fallback)
        if not include_all and label not in requested_perspectives:
            return
        if topic_lower:
            tags = seed.tags or []
            if not any(tag.lower() == topic_lower for tag in tags):
                return

        intersects = any(
            osis_intersects(seed.osis_a, requested)
            or osis_intersects(seed.osis_b, requested)
            for requested in candidates
        )
        if not intersects:
            return

        score = float(seed.weight or 0.0)
        scored.append(_ScoredSeed(seed=seed, score=score, perspective=label))

    for seed in contradiction_seeds:
        _consider(seed, fallback="skeptical")

    for seed in harmony_seeds:
        _consider(seed, fallback="apologetic")

    scored.sort(
        key=lambda entry: (
            -entry.score,
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
