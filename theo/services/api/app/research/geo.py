"""Lookup helpers for geographic reference data."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from sqlalchemy.orm import Session

from ..db.models import GeoPlace
from ..models.research import GeoPlaceItem


@dataclass(slots=True)
class _ScoredPlace:
    place: GeoPlace
    score: float


def _normalize(value: str) -> str:
    return value.casefold().strip()


def _candidate_strings(place: GeoPlace) -> Iterable[str]:
    yield place.slug
    yield place.name
    for alias in place.aliases or []:
        yield alias


def _fuzzy_score(query: str, candidate: str) -> float:
    if not candidate:
        return 0.0
    matcher = SequenceMatcher(a=query, b=candidate.casefold())
    return matcher.ratio()


def lookup_geo_places(
    session: Session,
    *,
    query: str,
    limit: int = 10,
) -> list[GeoPlaceItem]:
    """Return ranked geographic entries for the given query."""

    normalized_query = _normalize(query)
    if not normalized_query:
        return []

    places = session.query(GeoPlace).all()
    scored: list[_ScoredPlace] = []

    for place in places:
        best_score = 0.0
        for candidate in _candidate_strings(place):
            candidate_norm = candidate.casefold()
            if normalized_query in candidate_norm:
                best_score = max(best_score, 1.0)
                break
            best_score = max(best_score, _fuzzy_score(normalized_query, candidate_norm))
        if best_score <= 0.0:
            continue
        scored.append(_ScoredPlace(place=place, score=best_score))

    scored.sort(
        key=lambda entry: (
            -entry.score,
            -(entry.place.confidence or 0.0),
            entry.place.slug,
        )
    )

    items: list[GeoPlaceItem] = []
    for entry in scored[:limit]:
        place = entry.place
        items.append(
            GeoPlaceItem(
                slug=place.slug,
                name=place.name,
                lat=place.lat,
                lng=place.lng,
                confidence=place.confidence,
                aliases=list(place.aliases) if place.aliases else None,
                sources=place.sources,
            )
        )

    return items
