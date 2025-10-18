"""Builders for the analytics topic neighborhood graph."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from itertools import combinations
import math
from typing import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import (
    AnalyticsTopicMapEdge,
    AnalyticsTopicMapNode,
    AnalyticsTopicMapSnapshot,
    Document,
    Passage,
    TopicMapEdgeType,
    TopicMapNodeType,
)
from .topics import _extract_topics


def _normalise_topic(value: str) -> str:
    token = value.strip()
    if not token:
        return ""
    return token.lower()


def _average_vectors(vectors: Sequence[Sequence[float]]) -> list[float] | None:
    if not vectors:
        return None
    dimension = len(vectors[0])
    totals = [0.0] * dimension
    count = 0
    for vector in vectors:
        if len(vector) != dimension:
            continue
        for i, component in enumerate(vector):
            totals[i] += float(component)
        count += 1
    if count == 0:
        return None
    return [total / count for total in totals]


def _cosine_similarity(a: Sequence[float] | None, b: Sequence[float] | None) -> float:
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class TopicMapBuilder:
    """Compute and persist the global topic neighborhood graph."""

    def __init__(
        self,
        session: Session,
        *,
        similarity_threshold: float = 0.35,
    ):
        self.session = session
        self.similarity_threshold = max(0.0, float(similarity_threshold))

    def build(self, scope: str = "global") -> AnalyticsTopicMapSnapshot:
        documents = list(self.session.scalars(select(Document)))
        if not documents:
            snapshot = self._ensure_snapshot(scope)
            snapshot.generated_at = datetime.now(UTC)
            snapshot.parameters = {"similarity_threshold": self.similarity_threshold}
            snapshot.meta = {"document_count": 0, "topic_count": 0}
            self._clear_snapshot(snapshot)
            self.session.flush()
            return snapshot

        embeddings = self._load_document_embeddings(documents)
        if not embeddings:
            snapshot = self._ensure_snapshot(scope)
            snapshot.generated_at = datetime.now(UTC)
            snapshot.parameters = {"similarity_threshold": self.similarity_threshold}
            snapshot.meta = {"document_count": 0, "topic_count": 0}
            self._clear_snapshot(snapshot)
            self.session.flush()
            return snapshot

        topic_documents: dict[str, dict[str, object]] = defaultdict(lambda: {
            "label": "",
            "documents": set(),
            "embeddings": [],
            "titles": [],
        })

        for embedding in embeddings:
            doc_topics = [_normalise_topic(topic) for topic in embedding["topics"]]
            filtered_topics = [topic for topic in doc_topics if topic]
            if not filtered_topics:
                continue
            for topic_key, original in zip(filtered_topics, embedding["raw_topics"], strict=True):
                info = topic_documents[topic_key]
                if not info["label"]:
                    info["label"] = str(original).strip() or topic_key.title()
                info["documents"].add(embedding["document_id"])
                info["embeddings"].append(embedding["vector"])
                if embedding["title"]:
                    info["titles"].append(embedding["title"])

        if not topic_documents:
            snapshot = self._ensure_snapshot(scope)
            snapshot.generated_at = datetime.now(UTC)
            snapshot.parameters = {"similarity_threshold": self.similarity_threshold}
            snapshot.meta = {"document_count": len(embeddings), "topic_count": 0}
            self._clear_snapshot(snapshot)
            self.session.flush()
            return snapshot

        centroids: dict[str, list[float] | None] = {}
        for topic_key, info in topic_documents.items():
            centroid = _average_vectors(info["embeddings"])
            centroids[topic_key] = centroid
            info["centroid"] = centroid
            info["documents"] = sorted(info["documents"])
            info["titles"] = sorted({title for title in info["titles"] if title})

        snapshot = self._ensure_snapshot(scope)
        snapshot.generated_at = datetime.now(UTC)
        snapshot.parameters = {"similarity_threshold": self.similarity_threshold}
        snapshot.meta = {
            "document_count": len(embeddings),
            "topic_count": len(topic_documents),
        }
        self._clear_snapshot(snapshot)

        node_records: dict[str, AnalyticsTopicMapNode] = {}
        for topic_key in sorted(topic_documents):
            info = topic_documents[topic_key]
            label = info["label"] or topic_key.title()
            node = AnalyticsTopicMapNode(
                snapshot_id=snapshot.id,
                node_key=topic_key,
                node_type=TopicMapNodeType.TOPIC,
                label=label,
                weight=float(len(info["documents"])),
                embedding=info["centroid"],
                meta={
                    "documentIds": info["documents"],
                    "sampleTitles": info["titles"][:5],
                },
            )
            snapshot.nodes.append(node)
            node_records[topic_key] = node

        self.session.flush()

        for topic_a, topic_b in combinations(sorted(topic_documents), 2):
            info_a = topic_documents[topic_a]
            info_b = topic_documents[topic_b]
            shared = sorted(set(info_a["documents"]) & set(info_b["documents"]))
            similarity = _cosine_similarity(centroids.get(topic_a), centroids.get(topic_b))
            if similarity < self.similarity_threshold and not shared:
                continue
            edge_type = (
                TopicMapEdgeType.SEMANTIC
                if similarity >= self.similarity_threshold
                else TopicMapEdgeType.CO_OCCURRENCE
            )
            edge_weight = (
                float(round(similarity, 6))
                if edge_type is TopicMapEdgeType.SEMANTIC
                else float(len(shared))
            )
            edge = AnalyticsTopicMapEdge(
                snapshot_id=snapshot.id,
                src_node_id=node_records[topic_a].id,
                dst_node_id=node_records[topic_b].id,
                edge_type=edge_type,
                weight=edge_weight,
                meta={
                    "sharedDocuments": shared,
                    "similarity": round(similarity, 6),
                },
            )
            snapshot.edges.append(edge)

        self.session.flush()
        return snapshot

    def _load_document_embeddings(self, documents: Iterable[Document]) -> list[dict[str, object]]:
        doc_topics: dict[str, list[str]] = {}
        doc_titles: dict[str, str] = {}
        raw_topics: dict[str, list[str]] = {}
        for document in documents:
            extracted = _extract_topics(document)
            if not extracted:
                continue
            doc_topics[document.id] = [topic.strip() for topic in extracted if topic and topic.strip()]
            raw_topics[document.id] = list(doc_topics[document.id])
            doc_titles[document.id] = document.title or ""
        if not doc_topics:
            return []

        stmt = (
            select(Passage.document_id, Passage.embedding)
            .where(Passage.document_id.in_(list(doc_topics)))
            .where(Passage.embedding.isnot(None))
        )
        vectors: dict[str, list[Sequence[float]]] = defaultdict(list)
        for row in self.session.execute(stmt):
            vectors[row.document_id].append(row.embedding)

        result: list[dict[str, object]] = []
        for document_id, topics in doc_topics.items():
            doc_vectors = vectors.get(document_id)
            if not doc_vectors:
                continue
            centroid = _average_vectors(doc_vectors)
            if not centroid:
                continue
            result.append(
                {
                    "document_id": document_id,
                    "topics": topics,
                    "raw_topics": raw_topics.get(document_id, topics),
                    "title": doc_titles.get(document_id, ""),
                    "vector": centroid,
                }
            )
        return result

    def _ensure_snapshot(self, scope: str) -> AnalyticsTopicMapSnapshot:
        snapshot = self.session.scalar(
            select(AnalyticsTopicMapSnapshot).where(AnalyticsTopicMapSnapshot.scope == scope)
        )
        if snapshot is None:
            snapshot = AnalyticsTopicMapSnapshot(scope=scope)
            self.session.add(snapshot)
            self.session.flush()
        return snapshot

    def _clear_snapshot(self, snapshot: AnalyticsTopicMapSnapshot) -> None:
        if snapshot.id is None:
            return
        self.session.execute(
            delete(AnalyticsTopicMapEdge).where(AnalyticsTopicMapEdge.snapshot_id == snapshot.id)
        )
        self.session.execute(
            delete(AnalyticsTopicMapNode).where(AnalyticsTopicMapNode.snapshot_id == snapshot.id)
        )
        self.session.flush()


__all__ = ["TopicMapBuilder"]
