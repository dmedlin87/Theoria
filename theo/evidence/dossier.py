"""Generate high level reports for evidence collections."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Mapping

from .models import EvidenceCollection, EvidenceRecord
from .validator import EvidenceValidator


class EvidenceDossier:
    """Produce analytical summaries such as graph projections."""

    def __init__(self, validator: EvidenceValidator | None = None) -> None:
        self.validator = validator or EvidenceValidator()

    def collect(
        self,
        sources: Iterable[Path | str],
        *,
        tags: Sequence[str] | None = None,
        include_contradictions: bool = False,
    ) -> EvidenceCollection:
        """Validate ``sources`` and apply dossier-level filters."""

        collection = self.validator.validate_many(sources)
        records = self._filter_records(collection.records, tags, include_contradictions)
        return EvidenceCollection(records=tuple(records))

    def build_dossier(
        self,
        sources: Iterable[Path | str],
        *,
        mode: str = "records",
        tags: Sequence[str] | None = None,
        include_contradictions: bool = False,
        collection: EvidenceCollection | None = None,
    ) -> dict[str, object] | list[dict[str, object]]:
        """Generate dossier payloads for ``sources``."""

        effective_collection = (
            self.collect(sources, tags=tags, include_contradictions=include_contradictions)
            if collection is None
            else EvidenceCollection(
                records=tuple(
                    self._filter_records(collection.records, tags, include_contradictions)
                )
            )
        )

        records = [record.model_dump(mode="json") for record in effective_collection.records]
        mode = mode.lower()
        if mode == "records":
            return records
        tag_index = Counter(tag for record in effective_collection.records for tag in record.tags)
        osis_index = self._build_osis_index(effective_collection.records)
        summary: dict[str, object] = {
            "count": len(records),
            "tags": dict(sorted(tag_index.items())),
            "osis_index": osis_index,
            "records": records,
        }
        if mode == "summary":
            return summary
        if mode == "full":
            graph = self.build_graph(
                sources,
                tags=tags,
                include_contradictions=include_contradictions,
                collection=effective_collection,
            )
            summary["graph"] = graph
            return summary
        msg = f"Unsupported dossier mode: {mode}"
        raise ValueError(msg)

    def export_dossier(
        self,
        path: Path,
        *,
        mode: str = "records",
        tags: Sequence[str] | None = None,
        include_contradictions: bool = False,
        collection: EvidenceCollection | None = None,
        sources: Iterable[Path | str] | None = None,
    ) -> Path:
        """Persist a dossier to ``path`` and return the location."""

        if sources is None and collection is None:
            msg = "Either sources or a precomputed collection must be provided"
            raise ValueError(msg)
        payload = self.build_dossier(
            sources or (),
            mode=mode,
            tags=tags,
            include_contradictions=include_contradictions,
            collection=collection,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        path.write_text(text, encoding="utf-8")
        return path

    def build_graph(
        self,
        sources: Iterable[Path | str],
        *,
        format: str = "json",
        tags: Sequence[str] | None = None,
        include_contradictions: bool = False,
        collection: EvidenceCollection | None = None,
    ) -> dict[str, object] | str:
        """Return a graph representation for ``sources``."""

        effective_collection = (
            self.collect(sources, tags=tags, include_contradictions=include_contradictions)
            if collection is None
            else EvidenceCollection(
                records=tuple(
                    self._filter_records(collection.records, tags, include_contradictions)
                )
            )
        )

        adjacency: dict[str, set[str]] = defaultdict(set)
        for record in effective_collection.records:
            for osis in record.normalized_osis:
                adjacency[osis].add(record.sid)
        nodes = sorted(adjacency.keys())
        edges = [
            {"osis": osis, "records": sorted(sids)}
            for osis, sids in sorted(adjacency.items())
        ]
        graph = {
            "records": [record.model_dump(mode="json") for record in effective_collection.records],
            "nodes": nodes,
            "edges": edges,
        }
        if format.lower() == "json":
            return graph
        if format.lower() == "dot":
            return self._graph_to_dot(graph)
        msg = f"Unsupported graph format: {format}"
        raise ValueError(msg)

    def export_graph(
        self,
        path: Path,
        *,
        format: str = "json",
        tags: Sequence[str] | None = None,
        include_contradictions: bool = False,
        collection: EvidenceCollection | None = None,
        sources: Iterable[Path | str] | None = None,
    ) -> Path:
        """Persist a graph representation to ``path``."""

        if sources is None and collection is None:
            msg = "Either sources or a precomputed collection must be provided"
            raise ValueError(msg)
        payload = self.build_graph(
            sources or (),
            format=format,
            tags=tags,
            include_contradictions=include_contradictions,
            collection=collection,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, str):
            path.write_text(payload + ("\n" if not payload.endswith("\n") else ""), encoding="utf-8")
        else:
            text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
            path.write_text(text, encoding="utf-8")
        return path

    def _filter_records(
        self,
        records: Sequence[EvidenceRecord],
        tags: Sequence[str] | None,
        include_contradictions: bool,
    ) -> list[EvidenceRecord]:
        if not records:
            return []
        lowered_tags = {tag.lower() for tag in tags} if tags else None
        filtered: list[EvidenceRecord] = []
        for record in records:
            if lowered_tags and not lowered_tags.intersection(tag.lower() for tag in record.tags):
                continue
            if not include_contradictions and self._is_contradiction(record):
                continue
            filtered.append(record)
        return filtered

    def _is_contradiction(self, record: EvidenceRecord) -> bool:
        metadata = record.metadata
        status = str(metadata.get("status", "")) if isinstance(metadata, Mapping) else ""
        status = status.lower()
        if status in {"contradiction", "refuted"}:
            return True
        if any(tag.lower() in {"contradiction", "refuted"} for tag in record.tags):
            return True
        contradictions = metadata.get("contradictions") if isinstance(metadata, Mapping) else None
        if isinstance(contradictions, bool):
            return contradictions
        if isinstance(contradictions, Sequence) and contradictions:
            return True
        return False

    def _build_osis_index(self, records: Sequence[EvidenceRecord]) -> dict[str, list[str]]:
        index: dict[str, list[str]] = defaultdict(list)
        for record in records:
            for osis in record.normalized_osis:
                index[osis].append(record.sid)
        return {osis: sorted(sids) for osis, sids in sorted(index.items())}

    def _graph_to_dot(self, graph: Mapping[str, object]) -> str:
        nodes: Sequence[str] = graph.get("nodes", [])  # type: ignore[assignment]
        records: Sequence[Mapping[str, object]] = graph.get("records", [])  # type: ignore[assignment]
        edges: Sequence[Mapping[str, object]] = graph.get("edges", [])  # type: ignore[assignment]

        lines = ["digraph evidence {", "  graph [rankdir=LR];"]
        for osis in nodes:
            lines.append(f'  "{osis}" [shape=box];')
        for record in records:
            sid = str(record.get("sid", ""))
            title = str(record.get("title", ""))
            escaped_title = title.replace("\"", "\\\"")
            lines.append(f'  "{sid}" [shape=ellipse, label="{escaped_title}"];')
        for edge in edges:
            osis = str(edge.get("osis"))
            for sid in edge.get("records", []):  # type: ignore[assignment]
                lines.append(f'  "{osis}" -> "{sid}";')
        lines.append("}")
        return "\n".join(lines)


__all__ = ["EvidenceDossier"]
