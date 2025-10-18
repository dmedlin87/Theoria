"""Neighborhood reasoner deriving doctrine and topic tags."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

import importlib

from theo.adapters.graph import CaseGraphAdapter, GraphEdge, GraphNeighborhood

from .events import DocumentPersistedEvent


@dataclass(frozen=True, slots=True)
class InferredLabel:
    """Label score emitted by the reasoner."""

    value: str
    score: float
    count: int

    def to_dict(self) -> dict[str, object]:
        return {"value": self.value, "score": self.score, "count": self.count}


@dataclass(frozen=True, slots=True)
class ClusterScores:
    """Aggregated analytics for a connected neighbourhood cluster."""

    cluster_id: str
    member_ids: list[str]
    doctrine_scores: list[InferredLabel]
    topic_scores: list[InferredLabel]
    domain_scores: list[InferredLabel]

    def to_dict(self) -> dict[str, object]:
        return {
            "cluster_id": self.cluster_id,
            "member_ids": list(self.member_ids),
            "doctrine_scores": [label.to_dict() for label in self.doctrine_scores],
            "topic_scores": [label.to_dict() for label in self.topic_scores],
            "domain_scores": [label.to_dict() for label in self.domain_scores],
        }


@dataclass(frozen=True, slots=True)
class ReasonerReport:
    """Summary describing updates performed by the reasoner."""

    document_id: str
    updated_case_objects: list[str]
    clusters: Mapping[str, ClusterScores]


class GraphAdapterProtocol(Protocol):
    """Protocol implemented by graph adapters consumed by the reasoner."""

    def load_neighborhood(self, document_id: str) -> GraphNeighborhood: ...


def _build_adjacency(edges: Sequence[GraphEdge]) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, set()).add(edge.target)
        adjacency.setdefault(edge.target, set()).add(edge.source)
    return adjacency


def _connected_component(adjacency: Mapping[str, set[str]], seed: str) -> set[str]:
    stack = [seed]
    visited: set[str] = set()
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        stack.extend(neighbour for neighbour in adjacency.get(node, set()) if neighbour not in visited)
    return visited


def _cluster_identifier(member_ids: Iterable[str]) -> str:
    joined = ",".join(sorted(member_ids))
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
    return f"cluster:{digest}"


def _count_labels(values: Iterable[str]) -> tuple[dict[str, int], dict[str, str]]:
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for value in values:
        if not value:
            continue
        text = value.strip()
        if not text:
            continue
        key = text.lower()
        counts[key] = counts.get(key, 0) + 1
        labels.setdefault(key, text)
    return counts, labels


def _score_labels(
    counts: Mapping[str, int],
    labels: Mapping[str, str],
    *,
    denominator: int,
) -> list[InferredLabel]:
    if denominator <= 0:
        return []
    scored: list[InferredLabel] = []
    for key, count in counts.items():
        value = labels.get(key)
        if not value:
            continue
        score = round(count / denominator, 4)
        scored.append(InferredLabel(value=value, score=score, count=count))
    return sorted(scored, key=lambda item: item.score, reverse=True)


_MODELS = importlib.import_module("theo.adapters.persistence.models")
CaseObject = getattr(_MODELS, "CaseObject")
Session = Any


class NeighborhoodReasoner:
    """Reasoner assigning doctrine/topic tags based on neighbourhood graphs."""

    def __init__(
        self,
        *,
        graph_adapter_factory: Callable[[Session], GraphAdapterProtocol] | None = None,
        doctrine_threshold: float = 0.45,
        topic_threshold: float = 0.35,
        domain_threshold: float = 0.35,
    ) -> None:
        self._graph_adapter_factory = graph_adapter_factory or (lambda session: CaseGraphAdapter(session))
        self._doctrine_threshold = doctrine_threshold
        self._topic_threshold = topic_threshold
        self._domain_threshold = domain_threshold

    def handle_document_persisted(
        self, session: Session, event: DocumentPersistedEvent
    ) -> ReasonerReport:
        """Consume a persistence event and update neighbourhood analytics."""

        adapter = self._graph_adapter_factory(session)
        neighborhood = adapter.load_neighborhood(event.document_id)

        if not neighborhood.focus_ids:
            return ReasonerReport(event.document_id, updated_case_objects=[], clusters={})

        adjacency = _build_adjacency(neighborhood.edges)

        remaining = set(neighborhood.nodes)
        clusters: dict[str, ClusterScores] = {}
        node_cluster_map: dict[str, str] = {}

        for node_id in list(remaining):
            if node_id not in remaining:
                continue
            component = _connected_component(adjacency, node_id)
            remaining.difference_update(component)

            cluster_scores = self._score_cluster(component, neighborhood)
            clusters[cluster_scores.cluster_id] = cluster_scores
            for member in component:
                node_cluster_map[member] = cluster_scores.cluster_id

        updated_ids: list[str] = []
        for case_object_id in neighborhood.focus_ids:
            cluster_id = node_cluster_map.get(case_object_id)
            if not cluster_id:
                continue
            cluster = clusters[cluster_id]
            inference = self._build_inference(cluster)
            changed = self._apply_inference(
                session,
                case_object_id,
                inference,
                cluster,
                event,
            )
            if changed:
                updated_ids.append(case_object_id)

        return ReasonerReport(
            event.document_id,
            updated_case_objects=updated_ids,
            clusters=clusters,
        )

    def _score_cluster(
        self, members: Iterable[str], neighborhood: GraphNeighborhood
    ) -> ClusterScores:
        member_ids = sorted(set(members))
        nodes = neighborhood.nodes
        doctrine_values: list[str] = []
        topic_values: list[str] = []
        domain_values: list[str] = []

        for member_id in member_ids:
            node = nodes.get(member_id)
            if node is None:
                continue
            if node.doctrine:
                doctrine_values.append(node.doctrine)
            topic_values.extend(node.topics)
            domain_values.extend(node.topic_domains)

        denominator = max(len(member_ids), 1)
        doctrine_counts, doctrine_labels = _count_labels(doctrine_values)
        topic_counts, topic_labels = _count_labels(topic_values)
        domain_counts, domain_labels = _count_labels(domain_values)

        doctrine_scores = _score_labels(doctrine_counts, doctrine_labels, denominator=denominator)
        topic_scores = _score_labels(topic_counts, topic_labels, denominator=denominator)
        domain_scores = _score_labels(domain_counts, domain_labels, denominator=denominator)

        cluster_id = _cluster_identifier(member_ids)
        return ClusterScores(
            cluster_id=cluster_id,
            member_ids=member_ids,
            doctrine_scores=doctrine_scores,
            topic_scores=topic_scores,
            domain_scores=domain_scores,
        )

    def _build_inference(self, cluster: ClusterScores) -> list[dict[str, object]]:
        inferred: list[dict[str, object]] = []
        for label in cluster.doctrine_scores:
            if label.score < self._doctrine_threshold:
                continue
            inferred.append(
                {"type": "doctrine", "value": label.value, "score": label.score}
            )
        for label in cluster.domain_scores:
            if label.score < self._domain_threshold:
                continue
            inferred.append(
                {"type": "topic_domain", "value": label.value, "score": label.score}
            )
        for label in cluster.topic_scores:
            if label.score < self._topic_threshold:
                continue
            inferred.append(
                {"type": "topic", "value": label.value, "score": label.score}
            )
        return inferred

    def _apply_inference(
        self,
        session: Session,
        case_object_id: str,
        inferred_tags: list[dict[str, object]],
        cluster: ClusterScores,
        event: DocumentPersistedEvent,
    ) -> bool:
        if (
            not inferred_tags
            and not cluster.doctrine_scores
            and not cluster.topic_scores
            and not cluster.domain_scores
        ):
            return False

        case_object = session.get(CaseObject, case_object_id)
        if case_object is None:
            return False

        existing_meta = case_object.meta if isinstance(case_object.meta, dict) else {}
        existing_tags = list(case_object.tags or [])

        reasoner_meta = {
            "clusters": [cluster.to_dict()],
            "inferred_tags": inferred_tags,
            "event": event.to_payload(),
            "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }

        if existing_meta.get("reasoner") == reasoner_meta and not inferred_tags:
            return False

        merged_meta = dict(existing_meta)
        merged_meta["reasoner"] = reasoner_meta
        case_object.meta = merged_meta

        tags_changed = False
        for tag in inferred_tags:
            label = str(tag.get("value", "")).strip()
            kind = str(tag.get("type", "")).strip()
            if not label or not kind:
                continue
            tag_value = f"reasoner:{kind}:{label}"
            if tag_value not in existing_tags:
                existing_tags.append(tag_value)
                tags_changed = True

        if tags_changed:
            case_object.tags = existing_tags

        session.add(case_object)
        return True


__all__ = [
    "ClusterScores",
    "InferredLabel",
    "NeighborhoodReasoner",
    "ReasonerReport",
]

