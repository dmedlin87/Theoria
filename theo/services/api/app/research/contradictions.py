from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from sqlalchemy.orm import Session

from ..db.models import ContradictionSeed, HarmonySeed
from ..ingest.osis import osis_intersects
from ..models.research import ContradictionItem


@dataclass(slots=True)
class _ScoredSeed:
    id: str
    osis_a: str
    osis_b: str
    summary: str | None
    source: str | None
    tags: list[str] | None
    perspective: str
    score: float


def _normalize_osis(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if not value:
            continue
        normalized.append(value.strip())
    return normalized


def _matches_topic(tags: list[str] | None, topic_lower: str | None) -> bool:
    if topic_lower is None:
        return True
    if not tags:
        return False
    return any(tag.lower() == topic_lower for tag in tags)


def _intersects_any(seed_osis_a: str, seed_osis_b: str, candidates: list[str]) -> bool:
    return any(
        osis_intersects(seed_osis_a, requested)
        or osis_intersects(seed_osis_b, requested)
        for requested in candidates
    )


def search_contradictions(
    session: Session,
    *,
    osis: str | list[str],
    topic: str | None = None,
    perspectives: Sequence[str] | None = None,
    limit: int = 25,
) -> list[ContradictionItem]:
    """Return ranked contradiction or harmony entries intersecting the provided OSIS."""

    candidates = _normalize_osis([osis] if isinstance(osis, str) else osis)
    if not candidates:
        return []

    normalized_perspectives = {
        perspective.strip().lower() for perspective in perspectives or [] if perspective
    }
    include_skeptical = not normalized_perspectives or "skeptical" in normalized_perspectives
    include_apologetic = not normalized_perspectives or "apologetic" in normalized_perspectives
    topic_lower = topic.lower() if topic else None

    scored: list[_ScoredSeed] = []

    if include_skeptical:
        for seed in session.query(ContradictionSeed).all():
            perspective = (seed.perspective or "skeptical").lower()
            if normalized_perspectives and perspective not in normalized_perspectives:
                continue
            tags = list(seed.tags) if seed.tags else None
            if not _matches_topic(tags, topic_lower):
                continue
            if not _intersects_any(seed.osis_a, seed.osis_b, candidates):
                continue
            scored.append(
                _ScoredSeed(
                    id=seed.id,
                    osis_a=seed.osis_a,
                    osis_b=seed.osis_b,
                    summary=seed.summary,
                    source=seed.source,
                    tags=tags,
                    perspective=perspective,
                    score=float(seed.weight or 0.0),
                )
            )

    if include_apologetic:
        for seed in session.query(HarmonySeed).all():
            perspective = (seed.perspective or "apologetic").lower()
            if normalized_perspectives and perspective not in normalized_perspectives:
                continue
            tags = list(seed.tags) if seed.tags else None
            if not _matches_topic(tags, topic_lower):
                continue
            if not _intersects_any(seed.osis_a, seed.osis_b, candidates):
                continue
            scored.append(
                _ScoredSeed(
                    id=seed.id,
                    osis_a=seed.osis_a,
                    osis_b=seed.osis_b,
                    summary=seed.summary,
                    source=seed.source,
                    tags=tags,
                    perspective=perspective,
                    score=float(seed.weight or 0.0),
                )
            )

    scored.sort(key=lambda entry: (-entry.score, entry.summary or "", entry.id))

    items: list[ContradictionItem] = []
    for entry in scored[:limit]:
        items.append(
            ContradictionItem(
                id=entry.id,
                osis_a=entry.osis_a,
                osis_b=entry.osis_b,
                summary=entry.summary,
                source=entry.source,
                tags=entry.tags,
                weight=float(entry.score),
                perspective=entry.perspective,
            )
        )

    return items
