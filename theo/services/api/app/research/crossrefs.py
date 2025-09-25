"""Cross-reference helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .datasets import crossref_dataset


@dataclass(slots=True)
class CrossReferenceEntry:
    source: str
    target: str
    weight: float | None = None
    relation_type: str | None = None
    summary: str | None = None
    dataset: str | None = None


def fetch_cross_references(osis: str, limit: int = 25) -> list[CrossReferenceEntry]:
    """Return ranked cross-references for the supplied OSIS reference."""

    entries = crossref_dataset().get(osis, [])
    result = [
        CrossReferenceEntry(
            source=osis,
            target=entry["target"],
            weight=entry.get("weight"),
            relation_type=entry.get("relation_type"),
            summary=entry.get("summary"),
            dataset=entry.get("dataset"),
        )
        for entry in entries
    ]
    return result[:limit]
