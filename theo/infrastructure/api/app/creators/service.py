"""Helpers for querying creator profiles and transcript-derived claims."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from theo.infrastructure.api.app.persistence_models import (
    Creator,
    CreatorClaim,
    TranscriptQuote,
)


@dataclass(slots=True)
class CreatorTopicProfileData:
    """Aggregate view of a creator's stance and supporting quotes for a topic."""

    creator: Creator
    topic: str
    stance: str | None
    confidence: float | None
    quotes: list[TranscriptQuote]
    claims: list[CreatorClaim]


def search_creators(
    session: Session, *, query: str | None, limit: int
) -> list[Creator]:
    """Return creators matching *query* ordered by name."""

    stmt = session.query(Creator)
    if query:
        pattern = f"%{query.strip()}%"
        stmt = stmt.filter(Creator.name.ilike(pattern))
    return stmt.order_by(Creator.name.asc()).limit(limit).all()


def _normalise_topic(topic: str) -> str:
    cleaned = topic.strip()
    if not cleaned:
        raise ValueError("topic cannot be blank")
    return cleaned


def _resolve_stance(claims: Iterable[CreatorClaim]) -> str | None:
    counter: Counter[str] = Counter()
    for claim in claims:
        if claim.stance:
            counter[claim.stance.lower()] += 1
    if not counter:
        return None
    most_common = counter.most_common(1)[0][0]
    return most_common


def _average_confidence(claims: Iterable[CreatorClaim]) -> float | None:
    confidences = [claim.confidence for claim in claims if claim.confidence is not None]
    if not confidences:
        return None
    return float(sum(confidences) / len(confidences))


def _collect_quotes(
    claims: Iterable[CreatorClaim], limit: int
) -> list[TranscriptQuote]:
    quotes: list[TranscriptQuote] = []
    seen: set[str] = set()
    for claim in claims:
        segment = claim.segment
        if segment is None:
            continue
        ordered_quotes = sorted(
            segment.quotes,
            key=lambda quote: (
                -(quote.salience or 0.0),
                quote.created_at,
            ),
        )
        for quote in ordered_quotes:
            if quote.id in seen:
                continue
            quotes.append(quote)
            seen.add(quote.id)
            if len(quotes) >= limit:
                return quotes
    return quotes


def fetch_creator_topic_profile(
    session: Session,
    *,
    creator_id: str,
    topic: str,
    limit: int,
) -> CreatorTopicProfileData:
    """Load stance, claims, and quotes for *creator_id* on *topic*."""

    creator = session.get(Creator, creator_id)
    if creator is None:
        raise LookupError(f"Unknown creator: {creator_id}")

    topic_value = _normalise_topic(topic)
    claims = (
        session.query(CreatorClaim)
        .filter(CreatorClaim.creator_id == creator_id)
        .filter(func.lower(CreatorClaim.topic) == topic_value.lower())
        .order_by(CreatorClaim.created_at.desc())
        .all()
    )

    stance = _resolve_stance(claims)
    confidence = _average_confidence(claims)
    quotes = _collect_quotes(claims, limit)

    return CreatorTopicProfileData(
        creator=creator,
        topic=topic_value,
        stance=stance,
        confidence=confidence,
        quotes=quotes,
        claims=list(claims),
    )
