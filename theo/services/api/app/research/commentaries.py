"""Service helpers for commentary excerpt discovery."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..db.models import CommentaryExcerptSeed
from ..ingest.osis import expand_osis_reference, osis_intersects
from ..db.verse_graph import (
    compute_verse_id_ranges,
    query_commentary_seed_rows,
)
from ..models.research import CommentaryExcerptItem


def _normalize_osis(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if not value:
            continue
        normalized.append(value.strip())
    return normalized


def _normalize_perspective(value: str | None, *, default: str = "neutral") -> str:
    normalized = (value or default).strip().lower()
    if normalized not in {"apologetic", "skeptical", "neutral"}:
        return default
    return normalized


def search_commentaries(
    session: Session,
    *,
    osis: str | list[str],
    perspectives: list[str] | None = None,
    limit: int = 50,
) -> list[CommentaryExcerptItem]:
    """Return curated commentary excerpts intersecting an OSIS reference."""

    candidates = _normalize_osis([osis] if isinstance(osis, str) else osis)
    if not candidates:
        return []

    allowed_perspectives = {
        p.strip().lower()
        for p in (perspectives or [])
        if p and p.strip().lower() in {"apologetic", "skeptical", "neutral"}
    }
    if perspectives and not allowed_perspectives:
        return []

    candidate_ranges: list[tuple[str, int, int]] = []
    for requested in candidates:
        verse_ids = expand_osis_reference(requested)
        if not verse_ids:
            continue
        candidate_ranges.append((requested, min(verse_ids), max(verse_ids)))
    if not candidate_ranges:
        return []

    seed_query = session.query(CommentaryExcerptSeed)
    if allowed_perspectives:
        seed_query = seed_query.filter(
            CommentaryExcerptSeed.perspective.in_(list(allowed_perspectives))
        )

    range_predicates = [
        and_(
            CommentaryExcerptSeed.start_verse_id <= end,
            CommentaryExcerptSeed.end_verse_id >= start,
        )
        for _, start, end in candidate_ranges
    ]
    if range_predicates:
        seed_query = seed_query.filter(or_(*range_predicates))

    seeds = seed_query.all()
    windows = list(compute_verse_id_ranges(candidates).values())
    if not windows:
        return []

    seeds = query_commentary_seed_rows(session, windows)
    matched: list[CommentaryExcerptItem] = []

    for seed in seeds:
        perspective = _normalize_perspective(seed.perspective)
        if allowed_perspectives and perspective not in allowed_perspectives:
            continue

        matched.append(
            CommentaryExcerptItem(
                id=seed.id,
                osis=seed.osis,
                title=seed.title,
                excerpt=seed.excerpt,
                source=seed.source,
                perspective=perspective,
                tags=list(seed.tags) if seed.tags else None,
            )
        )

    matched.sort(
        key=lambda item: (
            item.perspective or "",
            item.title or "",
            item.id,
        )
    )
    return matched[:limit]
