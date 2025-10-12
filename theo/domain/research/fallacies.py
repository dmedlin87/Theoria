"""Heuristic fallacy detection helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .datasets import fallacy_dataset


@dataclass(frozen=True, slots=True)
class FallacyHit:
    id: str
    name: str
    category: str
    description: str
    severity: str | None
    confidence: float
    matches: list[str]


def _compute_confidence(keywords: Iterable[str], text: str) -> tuple[float, list[str]]:
    matches: list[str] = []
    confidence = 0.0
    lowered = text.lower()
    for keyword in keywords:
        if keyword.lower() in lowered:
            matches.append(keyword)
            confidence += 0.3
    return min(confidence, 1.0), matches


def fallacy_detect(
    text: str,
    *,
    min_confidence: float = 0.0,
) -> list[FallacyHit]:
    """Return heuristic fallacy detections for the supplied text."""

    stripped = text.strip()
    if not stripped:
        return []

    hits: list[FallacyHit] = []
    for raw in fallacy_dataset():
        confidence, matches = _compute_confidence(raw.get("keywords", []), stripped)
        if confidence < min_confidence or not matches:
            continue
        hits.append(
            FallacyHit(
                id=raw["id"],
                name=raw.get("name", raw["id"]),
                category=raw.get("category", ""),
                description=raw.get("description", ""),
                severity=raw.get("severity"),
                confidence=confidence,
                matches=matches,
            )
        )

    hits.sort(key=lambda item: item.confidence, reverse=True)
    return hits


__all__ = ["FallacyHit", "fallacy_detect"]
