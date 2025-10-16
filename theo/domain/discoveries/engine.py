from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence

import numpy as np
from sklearn.cluster import DBSCAN

from .models import (
    CorpusSnapshotSummary,
    DocumentEmbedding,
    PatternDiscovery,
)

"""Discovery engine that clusters embeddings to surface corpus patterns."""


def _normalise_topics(topics: Sequence[str]) -> list[str]:
    normalised: list[str] = []
    for topic in topics:
        if not topic:
            continue
        token = str(topic).strip()
        if not token:
            continue
        token = token.lower()
        if token not in normalised:
            normalised.append(token)
    return normalised


def _top_keywords(documents: Sequence[DocumentEmbedding], limit: int = 5) -> list[str]:
    counter: Counter[str] = Counter()
    for doc in documents:
        counter.update(_normalise_topics(doc.topics))
        if doc.metadata:
            keywords = doc.metadata.get("keywords")
            if isinstance(keywords, Iterable):
                counter.update(
                    _normalise_topics([str(value) for value in keywords if value])
                )
    return [keyword for keyword, _ in counter.most_common(limit)]


class PatternDiscoveryEngine:
    """Cluster embeddings using DBSCAN to detect document patterns."""

    def __init__(self, *, eps: float = 0.35, min_cluster_size: int = 3):
        self.eps = eps
        self.min_cluster_size = max(2, int(min_cluster_size))

    def detect(
        self, documents: Sequence[DocumentEmbedding]
    ) -> tuple[list[PatternDiscovery], CorpusSnapshotSummary]:
        """Return pattern discoveries and corpus statistics for *documents*."""

        filtered = [doc for doc in documents if doc.embedding]
        if len(filtered) < self.min_cluster_size:
            snapshot = self._build_snapshot(filtered, [])
            return [], snapshot

        embeddings = np.array([doc.embedding for doc in filtered], dtype=float)
        if not np.isfinite(embeddings).all():
            mask = np.isfinite(embeddings).all(axis=1)
            filtered = [doc for doc, keep in zip(filtered, mask, strict=False) if keep]
            embeddings = embeddings[mask]
        if len(filtered) < self.min_cluster_size:
            snapshot = self._build_snapshot(filtered, [])
            return [], snapshot

        clusterer = DBSCAN(eps=self.eps, min_samples=self.min_cluster_size, metric="cosine")
        labels = clusterer.fit_predict(embeddings)
        core_indices = set(getattr(clusterer, "core_sample_indices_", []))

        discoveries: list[PatternDiscovery] = []
        for label in sorted(set(labels)):
            if label < 0:
                continue
            member_indices = [idx for idx, candidate in enumerate(labels) if candidate == label]
            if len(member_indices) < self.min_cluster_size:
                continue
            members = [filtered[idx] for idx in member_indices]
            themes = _top_keywords(members, limit=5)
            cluster_strength = len(member_indices) / max(len(filtered), 1)
            core_members = len([idx for idx in member_indices if idx in core_indices])
            core_ratio = core_members / len(member_indices)
            confidence = min(0.95, round(0.5 + 0.4 * core_ratio + 0.1 * cluster_strength, 4))
            relevance = min(0.95, round(0.4 + 0.6 * cluster_strength, 4))
            title = (
                f"Pattern detected: {', '.join(theme.title() for theme in themes[:3])}"
                if themes
                else f"Pattern detected across {len(member_indices)} documents"
            )
            summary_topics = ", ".join(theme.title() for theme in themes[:5])
            doc_titles = [doc.title for doc in members if doc.title]
            description_fragments: list[str] = [
                f"Detected a cluster of {len(member_indices)} documents with overlapping themes."
            ]
            if summary_topics:
                description_fragments.append(f"Shared themes include {summary_topics}.")
            if doc_titles:
                sample = ", ".join(doc_titles[:3])
                description_fragments.append(f"Examples: {sample}.")
            metadata = {
                "relatedDocuments": [doc.document_id for doc in members],
                "relatedTopics": themes,
                "patternData": {
                    "clusterSize": len(member_indices),
                    "sharedThemes": themes,
                    "keyVerses": sorted(
                        {
                            verse
                            for doc in members
                            for verse in doc.verse_ids
                        }
                    )[:20],
                },
                "titles": doc_titles,
            }
            discoveries.append(
                PatternDiscovery(
                    title=title,
                    description=" ".join(description_fragments).strip(),
                    confidence=confidence,
                    relevance_score=relevance,
                    metadata=metadata,
                )
            )

        snapshot = self._build_snapshot(filtered, discoveries)
        return discoveries, snapshot

    def _build_snapshot(
        self,
        documents: Sequence[DocumentEmbedding],
        discoveries: Sequence[PatternDiscovery],
    ) -> CorpusSnapshotSummary:
        verse_ids = {
            verse
            for doc in documents
            for verse in doc.verse_ids
            if isinstance(verse, int)
        }
        topic_counter: Counter[str] = Counter()
        for doc in documents:
            topic_counter.update(_normalise_topics(doc.topics))
        snapshot_metadata = {"pattern_cluster_count": len(discoveries)}
        return CorpusSnapshotSummary(
            document_count=len(documents),
            verse_coverage={
                "unique_count": len(verse_ids),
                "sample": sorted(list(verse_ids))[:20],
            },
            dominant_themes={
                "top_topics": [topic for topic, _ in topic_counter.most_common(10)]
            },
            metadata=snapshot_metadata,
        )


__all__ = ["PatternDiscoveryEngine"]
