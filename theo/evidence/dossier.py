"""Generate high level reports for evidence collections."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from .validator import EvidenceValidator


class EvidenceDossier:
    """Produce analytical summaries such as graph projections."""

    def __init__(self, validator: EvidenceValidator | None = None) -> None:
        self.validator = validator or EvidenceValidator()

    def build_graph(self, sources: Iterable[Path | str]) -> dict[str, object]:
        """Return a lightweight graph representation for ``sources``."""

        collection = self.validator.validate_many(sources)
        adjacency: dict[str, set[str]] = defaultdict(set)
        for record in collection.records:
            for osis in record.normalized_osis:
                adjacency[osis].add(record.sid)
        nodes = sorted(adjacency.keys())
        edges = [
            {"osis": osis, "records": sorted(sids)}
            for osis, sids in sorted(adjacency.items())
        ]
        return {
            "records": [record.model_dump(mode="json") for record in collection.records],
            "nodes": nodes,
            "edges": edges,
        }


__all__ = ["EvidenceDossier"]
