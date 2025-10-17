"""Adapters exposing graph neighbourhoods for reasoner workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from theo.adapters.persistence.models import CaseEdge, CaseObject, Document


def _deduplicate(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value:
            continue
        text = value.strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(text)
    return ordered


def _extract_topics(document: Document | None) -> list[str]:
    if document is None:
        return []

    raw = document.topics
    collected: list[str] = []
    if isinstance(raw, list):
        collected.extend(str(item) for item in raw if item)
    elif isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, list):
                collected.extend(str(item) for item in value if item)
            elif isinstance(value, str):
                collected.append(value)
    return _deduplicate(collected)


def _extract_topic_domains(document: Document | None, case_object: CaseObject) -> list[str]:
    domains: list[str] = []
    if document and isinstance(document.topic_domains, list):
        domains.extend(str(item) for item in document.topic_domains if item)

    meta = case_object.meta or {}
    if isinstance(meta, dict):
        passage_meta = meta.get("passage_meta")
        if isinstance(passage_meta, dict):
            meta_domains = passage_meta.get("topic_domains")
            if isinstance(meta_domains, list):
                domains.extend(str(item) for item in meta_domains if item)
    return _deduplicate(domains)


def _extract_tradition(document: Document | None, case_object: CaseObject) -> str | None:
    if document and document.theological_tradition:
        return str(document.theological_tradition)
    meta = case_object.meta or {}
    if isinstance(meta, dict):
        passage_meta = meta.get("passage_meta")
        if isinstance(passage_meta, dict):
            raw = passage_meta.get("theological_tradition")
            if raw:
                text = str(raw).strip()
                if text:
                    return text
    return None


@dataclass(frozen=True, slots=True)
class GraphNode:
    """Node metadata required by the reasoner."""

    id: str
    document_id: str | None
    topics: list[str]
    topic_domains: list[str]
    doctrine: str | None
    is_focus: bool


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """Edge metadata describing relationships between CaseObjects."""

    source: str
    target: str
    kind: str
    weight: float | None


@dataclass(frozen=True, slots=True)
class GraphNeighborhood:
    """Subgraph anchored on CaseObjects from a single document."""

    focus_ids: list[str]
    nodes: dict[str, GraphNode]
    edges: list[GraphEdge]


class CaseGraphAdapter:
    """Adapter building graph neighbourhoods from Case Builder tables."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def load_neighborhood(self, document_id: str) -> GraphNeighborhood:
        """Return neighbourhood data for CaseObjects attached to *document_id*."""

        focus_stmt = (
            select(CaseObject)
            .options(joinedload(CaseObject.document))
            .where(CaseObject.document_id == document_id)
        )
        focus_objects = list(self._session.execute(focus_stmt).scalars().all())

        focus_ids = [obj.id for obj in focus_objects]
        if not focus_ids:
            return GraphNeighborhood(focus_ids=[], nodes={}, edges=[])

        edge_stmt = select(CaseEdge).where(
            or_(
                CaseEdge.src_object_id.in_(focus_ids),
                CaseEdge.dst_object_id.in_(focus_ids),
            )
        )
        edges = list(self._session.execute(edge_stmt).scalars().all())

        neighbour_ids = {edge.src_object_id for edge in edges}
        neighbour_ids.update(edge.dst_object_id for edge in edges)
        all_ids = _deduplicate([*focus_ids, *neighbour_ids])

        if not all_ids:
            nodes = {
                obj.id: GraphNode(
                    id=obj.id,
                    document_id=obj.document_id,
                    topics=_extract_topics(obj.document),
                    topic_domains=_extract_topic_domains(obj.document, obj),
                    doctrine=_extract_tradition(obj.document, obj),
                    is_focus=True,
                )
                for obj in focus_objects
            }
            return GraphNeighborhood(focus_ids=focus_ids, nodes=nodes, edges=[])

        neighbourhood_stmt = (
            select(CaseObject)
            .options(joinedload(CaseObject.document))
            .where(CaseObject.id.in_(all_ids))
        )
        objects = {
            obj.id: obj
            for obj in self._session.execute(neighbourhood_stmt).scalars().all()
        }

        nodes: dict[str, GraphNode] = {}
        for object_id, obj in objects.items():
            nodes[object_id] = GraphNode(
                id=object_id,
                document_id=obj.document_id,
                topics=_extract_topics(obj.document),
                topic_domains=_extract_topic_domains(obj.document, obj),
                doctrine=_extract_tradition(obj.document, obj),
                is_focus=object_id in focus_ids,
            )

        for obj in focus_objects:
            if obj.id not in nodes:
                nodes[obj.id] = GraphNode(
                    id=obj.id,
                    document_id=obj.document_id,
                    topics=_extract_topics(obj.document),
                    topic_domains=_extract_topic_domains(obj.document, obj),
                    doctrine=_extract_tradition(obj.document, obj),
                    is_focus=True,
                )

        edge_payload: list[GraphEdge] = []
        for edge in edges:
            src = edge.src_object_id
            dst = edge.dst_object_id
            if src not in nodes or dst not in nodes:
                continue
            kind = edge.kind.value if hasattr(edge.kind, "value") else str(edge.kind)
            edge_payload.append(
                GraphEdge(source=src, target=dst, kind=kind, weight=edge.weight)
            )

        return GraphNeighborhood(focus_ids=focus_ids, nodes=nodes, edges=edge_payload)


__all__ = [
    "CaseGraphAdapter",
    "GraphEdge",
    "GraphNeighborhood",
    "GraphNode",
]

