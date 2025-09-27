"""Dead Sea Scroll linkage helpers."""

from dataclasses import dataclass
from typing import Iterable

from .datasets import dss_linkages_dataset


@dataclass(slots=True)
class DeadSeaScrollLink:
    id: str
    fragment: str
    scroll: str | None
    summary: str | None
    source: str | None
    url: str | None


def fetch_dead_sea_scroll_links(osis: str) -> list[DeadSeaScrollLink]:
    """Return Dead Sea Scroll fragments linked to a verse."""

    dataset = dss_linkages_dataset()
    entries: Iterable[dict[str, object]] = dataset.get(osis, [])
    links: list[DeadSeaScrollLink] = []
    for raw in entries:
        links.append(
            DeadSeaScrollLink(
                id=str(raw.get("id") or f"dss-{osis}"),
                fragment=str(raw.get("fragment") or "Unknown fragment"),
                scroll=str(raw.get("scroll")) if raw.get("scroll") is not None else None,
                summary=str(raw.get("summary")) if raw.get("summary") is not None else None,
                source=str(raw.get("source")) if raw.get("source") is not None else None,
                url=str(raw.get("url")) if raw.get("url") is not None else None,
            )
        )
    return links
