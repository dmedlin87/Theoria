"""Helpers for querying bundled historicity citations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .datasets import historicity_dataset


@dataclass(slots=True)
class HistoricityEntry:
    id: str
    title: str
    authors: list[str]
    year: int | None
    summary: str | None
    source: str | None
    url: str | None
    tags: list[str]
    score: float


def _score_entry(query_tokens: Iterable[str], entry: dict[str, object]) -> float:
    """Return a simple keyword overlap score for ranking results."""

    haystack_parts: list[str] = []
    title = entry.get("title", "") or ""
    summary = entry.get("summary", "") or ""
    tags = " ".join(entry.get("tags", []))
    haystack_parts.append(title)
    haystack_parts.append(summary)
    haystack_parts.append(tags)
    haystack = " ".join(haystack_parts).lower()
    return sum(1.0 for token in query_tokens if token in haystack)


def historicity_search(
    query: str,
    *,
    year_from: int | None = None,
    year_to: int | None = None,
    limit: int = 20,
) -> list[HistoricityEntry]:
    """Return ranked citation entries for a topical query."""

    tokens = {token for token in query.lower().split() if token}
    if not tokens:
        return []

    entries: list[HistoricityEntry] = []
    for raw in historicity_dataset():
        year = raw.get("year")
        if year_from is not None and isinstance(year, int) and year < year_from:
            continue
        if year_to is not None and isinstance(year, int) and year > year_to:
            continue

        score = _score_entry(tokens, raw)
        if score == 0:
            continue

        entries.append(
            HistoricityEntry(
                id=raw["id"],
                title=raw.get("title", ""),
                authors=list(raw.get("authors", [])),
                year=year if isinstance(year, int) else None,
                summary=raw.get("summary"),
                source=raw.get("source"),
                url=raw.get("url"),
                tags=list(raw.get("tags", [])),
                score=score,
            )
        )

    entries.sort(key=lambda item: item.score, reverse=True)
    return entries[:limit]
