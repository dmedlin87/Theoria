"""Helpers for retrieving textual variant apparatus entries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .datasets import variants_dataset


@dataclass(frozen=True, slots=True)
class VariantEntry:
    id: str
    osis: str
    category: str
    reading: str
    note: str | None = None
    source: str | None = None
    witness: str | None = None
    translation: str | None = None
    confidence: float | None = None
    dataset: str | None = None
    disputed: bool | None = None
    witness_metadata: dict[str, object] | None = None


def _expand_osis(osis: str) -> list[str]:
    """Expand a verse or simple range into individual OSIS keys."""

    if "-" not in osis:
        return [osis]

    start, end = osis.split("-", 1)
    if "." not in end:
        end = f"{start.rsplit('.', 1)[0]}.{end}"

    book_chapter = start.rsplit(".", 1)[0]
    start_idx = int(start.split(".")[-1])
    end_idx = int(end.split(".")[-1])
    return [f"{book_chapter}.{idx}" for idx in range(start_idx, end_idx + 1)]


def variants_apparatus(
    osis: str,
    *,
    categories: Iterable[str] | None = None,
    limit: int | None = None,
) -> list[VariantEntry]:
    """Return apparatus entries for the supplied reference."""

    normalized_categories = {c.lower() for c in categories or []} or None
    dataset = variants_dataset()
    osis_keys = _expand_osis(osis)

    entries: list[VariantEntry] = []
    for key in osis_keys:
        for raw in dataset.get(key, []):
            category = raw.get("category", "note")
            if normalized_categories and category.lower() not in normalized_categories:
                continue
            entries.append(
                VariantEntry(
                    id=raw["id"],
                    osis=key,
                    category=category,
                    reading=raw["reading"],
                    note=raw.get("note"),
                    source=raw.get("source"),
                    witness=raw.get("witness"),
                    translation=raw.get("translation"),
                    confidence=raw.get("confidence"),
                    dataset=raw.get("dataset"),
                    disputed=raw.get("disputed"),
                    witness_metadata=raw.get("witness_metadata"),
                )
            )

    if limit is not None:
        entries = entries[:limit]

    return entries


__all__ = ["VariantEntry", "variants_apparatus"]
