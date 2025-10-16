"""Service helpers for contradiction discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from ..db.models import ContradictionSeed, HarmonySeed
from ..db.verse_graph import compute_verse_id_ranges, query_pair_seed_rows
from ..models.research import ContradictionItem

PERSPECTIVE_CHOICES: tuple[str, ...] = ("apologetic", "skeptical", "neutral")


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

    windows = list(compute_verse_id_ranges(candidates).values())
    if not windows:
        return []

    perspective_filter_active = bool(allowed_perspectives)
    include_contradictions = not perspective_filter_active or bool(
        allowed_perspectives & {"skeptical", "neutral"}
    )
    include_harmonies = not perspective_filter_active or bool(
        allowed_perspectives & {"apologetic", "neutral"}
    )

    contradiction_seeds: list[ContradictionSeed] = []
    harmony_seeds: list[HarmonySeed] = []

    if include_contradictions:
        contradiction_seeds = query_pair_seed_rows(session, windows, ContradictionSeed)
    if include_harmonies:
        harmony_seeds = query_pair_seed_rows(session, windows, HarmonySeed)
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

    for seed in contradiction_seeds:
        perspective = _normalize_perspective(seed.perspective, default="skeptical")
        if not _allowed_perspective(perspective):
            continue
        if not _should_include(seed.tags):
            continue

        score = float(seed.weight or 0.0)
        scored.append(_ScoredSeed(seed=seed, score=score, perspective=perspective))

    for seed in harmony_seeds:
        perspective = _normalize_perspective(seed.perspective, default="apologetic")
        if not _allowed_perspective(perspective):
            continue
        if not _should_include(seed.tags):
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
