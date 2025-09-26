"""Service helpers for contradiction discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from ..db.models import ContradictionSeed
from ..ingest.osis import osis_intersects
from ..models.research import ContradictionItem


@dataclass(slots=True)
class _ScoredSeed:
    seed: ContradictionSeed
    score: float


def _normalize_osis(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if not value:
            continue
        normalized.append(value.strip())
    return normalized


def search_contradictions(
    session: Session,
    *,
    osis: str | list[str],
    topic: str | None = None,
    limit: int = 25,
) -> list[ContradictionItem]:
    """Return ranked contradiction entries intersecting the provided OSIS."""

    candidates = _normalize_osis([osis] if isinstance(osis, str) else osis)
    if not candidates:
        return []

    seeds = session.query(ContradictionSeed).all()
    topic_lower = topic.lower() if topic else None
    scored: list[_ScoredSeed] = []

    for seed in seeds:
        if topic_lower:
            tags = seed.tags or []
            if not any(tag.lower() == topic_lower for tag in tags):
                continue

        intersects = any(
            osis_intersects(seed.osis_a, requested)
            or osis_intersects(seed.osis_b, requested)
            for requested in candidates
        )
        if not intersects:
            continue

        score = float(seed.weight or 0.0)
        scored.append(_ScoredSeed(seed=seed, score=score))

    scored.sort(
        key=lambda entry: (-entry.score, entry.seed.summary or "", entry.seed.id)
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
            )
        )

    return items
