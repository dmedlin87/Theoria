from __future__ import annotations

from typing import Iterable, Sequence

from sqlalchemy.orm import Session

from ..db.models import CommentaryExcerptSeed
from ..models.research import CommentaryExcerpt, CommentaryExcerptResponse


def _normalize(values: Iterable[str] | None) -> set[str]:
    if not values:
        return set()
    return {value.strip().lower() for value in values if value}


def get_commentary_excerpts(
    session: Session,
    *,
    osis: str,
    perspectives: Sequence[str] | None = None,
    limit: int = 25,
) -> CommentaryExcerptResponse:
    """Return curated commentary excerpts filtered by OSIS and perspective."""

    perspective_filter = _normalize(perspectives)
    query = session.query(CommentaryExcerptSeed).filter(CommentaryExcerptSeed.osis == osis)

    items: list[CommentaryExcerpt] = []
    for seed in query.order_by(CommentaryExcerptSeed.created_at.desc()).all():
        perspective = (seed.perspective or "neutral").lower()
        if perspective_filter and perspective not in perspective_filter:
            continue
        items.append(
            CommentaryExcerpt(
                id=seed.id,
                osis=seed.osis,
                title=seed.title,
                excerpt=seed.excerpt,
                source=seed.source,
                citation=seed.citation,
                tradition=seed.tradition,
                perspective=perspective,
                tags=list(seed.tags) if seed.tags else None,
            )
        )
        if len(items) >= limit:
            break

    return CommentaryExcerptResponse(osis=osis, items=items, total=len(items))
