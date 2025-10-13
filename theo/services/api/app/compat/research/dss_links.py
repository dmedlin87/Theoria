"""Compatibility re-export for Dead Sea Scroll linkage helpers."""
from __future__ import annotations

from importlib import import_module
from typing import Callable, Iterable
from warnings import warn

from theo.domain.research import dss_links as _domain_dss_links
from theo.domain.research.datasets import dss_links_dataset
from theo.domain.research.dss_links import DssLinkEntry

warn(
    "Importing from 'theo.services.api.app.research.dss_links' is deprecated; "
    "use 'theo.domain.research.dss_links' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["DssLinkEntry", "fetch_dss_links", "dss_links_dataset"]


def fetch_dss_links(osis: str) -> list[DssLinkEntry]:
    """Return Dead Sea Scroll links for an OSIS reference using legacy dataset hooks."""

    dataset_getter: Callable[[], dict[str, list[dict[str, object]]]] = dss_links_dataset
    try:
        legacy_module = import_module("theo.services.api.app.research.dss_links")
    except ModuleNotFoundError:  # pragma: no cover - defensive guard
        legacy_module = None
    if legacy_module is not None:
        override = getattr(legacy_module, "dss_links_dataset", None)
        if callable(override):
            dataset_getter = override

    dataset = dataset_getter()
    osis_keys: Iterable[str] = _domain_dss_links._expand_osis(osis)

    entries: list[DssLinkEntry] = []
    for key in osis_keys:
        for raw in dataset.get(key, []):
            url = raw.get("url")
            if not url:
                continue

            identifier = raw.get("id") or f"{key}:{len(entries)}"
            osis_value = raw.get("osis") or key

            entries.append(
                DssLinkEntry(
                    id=identifier,
                    osis=osis_value,
                    title=raw.get("title")
                    or raw.get("fragment")
                    or "Dead Sea Scrolls link",
                    url=url,
                    fragment=raw.get("fragment"),
                    summary=raw.get("summary"),
                    dataset=raw.get("dataset"),
                )
            )

    return entries
