from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .datasets import dss_links_dataset


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


@dataclass(slots=True)
class DssLinkEntry:
    id: str
    osis: str
    title: str
    url: str
    fragment: str | None = None
    summary: str | None = None
    dataset: str | None = None


def fetch_dss_links(osis: str) -> list[DssLinkEntry]:
    """Return Dead Sea Scrolls linkage entries for an OSIS reference."""

    dataset = dss_links_dataset()
    osis_keys: Iterable[str] = _expand_osis(osis)

    entries: list[DssLinkEntry] = []
    for key in osis_keys:
        for raw in dataset.get(key, []):
            entries.append(
                DssLinkEntry(
                    id=raw["id"],
                    osis=key,
                    title=raw.get("title") or raw.get("fragment") or "Dead Sea Scrolls link",
                    url=raw["url"],
                    fragment=raw.get("fragment"),
                    summary=raw.get("summary"),
                    dataset=raw.get("dataset"),
                )
            )

    return entries
