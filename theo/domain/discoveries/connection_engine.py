"""Connection discovery engine leveraging graph analysis with NetworkX."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Mapping, Sequence

import networkx as nx

from .models import DocumentEmbedding


@dataclass(frozen=True)
class ConnectionDiscovery:
    """A graph-derived relationship between documents."""

    title: str
    description: str
    confidence: float
    relevance_score: float
    metadata: Mapping[str, object] = field(default_factory=dict)


class ConnectionDiscoveryEngine:
    """Analyse shared references to surface strongly connected documents."""

    def __init__(
        self,
        *,
        min_shared_verses: int = 1,
        min_documents: int = 2,
        max_results: int = 10,
    ) -> None:
        if min_shared_verses < 1:
            raise ValueError("min_shared_verses must be at least 1")
        if min_documents < 2:
            raise ValueError("min_documents must be at least 2")
        if max_results < 1:
            raise ValueError("max_results must be positive")
        self.min_shared_verses = int(min_shared_verses)
        self.min_documents = int(min_documents)
        self.max_results = int(max_results)

    def detect(self, documents: Sequence[DocumentEmbedding]) -> list[ConnectionDiscovery]:
        """Return connection discoveries for *documents*."""

        verse_sets: dict[str, set[int]] = {}
        filtered: list[DocumentEmbedding] = []
        for doc in documents:
            verses = {verse for verse in doc.verse_ids if isinstance(verse, int)}
            if not verses:
                continue
            verse_sets[doc.document_id] = verses
            filtered.append(doc)

        if len(filtered) < self.min_documents:
            return []

        bipartite_graph = nx.Graph()
        document_nodes: list[tuple[str, str]] = []
        for doc in filtered:
            doc_node = ("document", doc.document_id)
            bipartite_graph.add_node(doc_node, bipartite=0, document=doc)
            document_nodes.append(doc_node)
            for verse in verse_sets[doc.document_id]:
                verse_node = ("verse", verse)
                bipartite_graph.add_node(verse_node, bipartite=1, verse=verse)
                bipartite_graph.add_edge(doc_node, verse_node)

        if not bipartite_graph.number_of_edges():
            return []

        projected = nx.algorithms.bipartite.weighted_projected_graph(
            bipartite_graph, document_nodes
        )
        pruned = nx.Graph()
        for node, data in projected.nodes(data=True):
            pruned.add_node(node, **data)

        for u, v, data in projected.edges(data=True):
            weight = int(data.get("weight", 0))
            if weight >= self.min_shared_verses:
                pruned.add_edge(u, v, weight=weight)

        if pruned.number_of_edges() == 0:
            return []

        discoveries: list[ConnectionDiscovery] = []
        for component_nodes in nx.connected_components(pruned):
            if len(component_nodes) < self.min_documents:
                continue
            subgraph = pruned.subgraph(component_nodes)
            docs = [
                bipartite_graph.nodes[node]["document"]
                for node in component_nodes
                if node in bipartite_graph
            ]
            if len(docs) < self.min_documents:
                continue

            verse_counter: Counter[int] = Counter()
            topic_counter: Counter[str] = Counter()
            for doc in docs:
                verse_counter.update(verse_sets.get(doc.document_id, set()))
                topic_counter.update(
                    self._normalise_topic(topic)
                    for topic in doc.topics
                    if isinstance(topic, str)
                )

            shared_verses = sorted(
                verse for verse, count in verse_counter.items() if count >= 2
            )
            if not shared_verses:
                continue

            shared_topics = [
                topic for topic, count in topic_counter.items() if count >= 2 and topic
            ][:5]

            edges_payload: list[dict[str, object]] = []
            edge_weights: list[int] = []
            for u, v, data in subgraph.edges(data=True):
                doc_a = bipartite_graph.nodes[u]["document"]
                doc_b = bipartite_graph.nodes[v]["document"]
                shared = sorted(
                    verse_sets[doc_a.document_id] & verse_sets[doc_b.document_id]
                )
                weight = int(data.get("weight", len(shared)))
                edge_weights.append(weight)
                edges_payload.append(
                    {
                        "documentA": doc_a.document_id,
                        "documentB": doc_b.document_id,
                        "sharedVerses": shared,
                        "sharedVerseCount": len(shared),
                        "weight": weight,
                    }
                )

            if not edge_weights:
                continue

            max_shared = max(edge_weights)
            density = nx.density(subgraph)
            confidence = min(
                0.95,
                round(0.45 + 0.1 * max_shared + 0.25 * density, 4),
            )
            relevance = min(
                0.9,
                round(
                    0.35
                    + 0.05 * len(docs)
                    + 0.05 * len(shared_verses)
                    + 0.05 * len(shared_topics),
                    4,
                ),
            )

            cleaned_titles = [
                (doc.title.strip() if isinstance(doc.title, str) else "") for doc in docs
            ]
            fallbacks = [doc.document_id for doc in docs]
            resolved_titles = [title or fallback for title, fallback in zip(cleaned_titles, fallbacks, strict=False)]
            if len(docs) == 2:
                title = (
                    f"Connection between {resolved_titles[0]} and {resolved_titles[1]}"
                )
            else:
                title = f"Connection cluster spanning {len(docs)} documents"

            shared_verse_preview = ", ".join(str(verse) for verse in shared_verses[:5])
            description_parts = [
                f"Detected a network of {len(docs)} documents linked by shared verses."
            ]
            if shared_verse_preview:
                description_parts.append(
                    f"Key shared verses include {shared_verse_preview}."
                )
            if shared_topics:
                description_parts.append(
                    "Common themes: " + ", ".join(topic.title() for topic in shared_topics)
                )

            metadata: dict[str, object] = {
                "relatedDocuments": [doc.document_id for doc in docs],
                "relatedVerses": shared_verses,
                "relatedTopics": shared_topics,
                "connectionData": {
                    "edgeList": edges_payload,
                    "graphDensity": round(density, 4),
                    "sharedVerseCount": len(shared_verses),
                    "maxSharedPerEdge": max_shared,
                },
            }

            discoveries.append(
                ConnectionDiscovery(
                    title=title,
                    description=" ".join(description_parts),
                    confidence=confidence,
                    relevance_score=relevance,
                    metadata=metadata,
                )
            )

        discoveries.sort(key=lambda item: (item.confidence, item.relevance_score), reverse=True)
        return discoveries[: self.max_results]

    @staticmethod
    def _normalise_topic(topic: str) -> str:
        token = topic.strip().lower()
        return token


__all__ = ["ConnectionDiscovery", "ConnectionDiscoveryEngine"]

