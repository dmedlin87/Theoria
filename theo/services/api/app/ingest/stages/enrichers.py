"""Enrichment stages for ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from . import Enricher


@dataclass(slots=True)
class DocumentEnricher(Enricher):
    """Attach derived document metadata before persistence."""

    default_title_factory: Callable[[dict[str, Any]], str]
    name: str = "document_enricher"

    def enrich(self, *, context, state: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        frontmatter = dict(state.get("frontmatter") or {})
        metadata = dict(state.get("document_metadata") or {})
        title = frontmatter.get("title") or self.default_title_factory(state)
        metadata.setdefault("title", title)
        metadata.setdefault("source_type", state.get("source_type"))
        if "sha256" in state and "sha256" not in metadata:
            metadata["sha256"] = state["sha256"]
        return {
            "frontmatter": frontmatter,
            "title": title,
            "document_metadata": metadata,
        }


@dataclass(slots=True)
class NoopEnricher(Enricher):
    """Enricher that forwards state without modification."""

    name: str = "noop_enricher"

    def enrich(self, *, context, state: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        return {}
