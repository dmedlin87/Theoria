"""Lookup helpers for commentary seed catalogues."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy.orm import Session

from ..db.models import CommentarySeed
from ..ingest.osis import osis_intersects
from ..models.research import CommentaryItem


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


def _seed_perspective(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized or "neutral"


def search_commentaries(
    session: Session,
    *,
    osis: str | list[str],
    perspective: str | list[str] | None = None,
    tag: str | None = None,
    limit: int = 25,
) -> list[CommentaryItem]:
    """Return commentary excerpts intersecting the requested OSIS references."""

    candidates = _normalize_osis([osis] if isinstance(osis, str) else osis)
    if not candidates:
        return []

    requested_perspectives = _normalize_perspectives(perspective)
    include_all = not requested_perspectives
    tag_lower = tag.lower() if tag else None

    seeds = session.query(CommentarySeed).all()
    selected: list[tuple[CommentarySeed, str]] = []

    for seed in seeds:
        label = _seed_perspective(getattr(seed, "perspective", None))
        if not include_all and label not in requested_perspectives:
            continue

        if tag_lower and seed.tags:
            if not any(str(item).strip().lower() == tag_lower for item in seed.tags):
                continue

        intersects = any(osis_intersects(seed.osis, requested) for requested in candidates)
        if not intersects:
            continue

        selected.append((seed, label))

    selected.sort(
        key=lambda entry: (
            entry[1],
            entry[0].title or "",
            entry[0].created_at if isinstance(entry[0].created_at, datetime) else datetime.now(UTC),
            entry[0].id,
        )
    )

    items: list[CommentaryItem] = []
    for seed, label in selected[:limit]:
        items.append(
            CommentaryItem(
                id=seed.id,
                osis=seed.osis,
                title=seed.title,
                excerpt=seed.excerpt,
                source=seed.source,
                citation=seed.citation,
                tags=list(seed.tags) if seed.tags else None,
                perspective=label,
            )
        )

    return items
