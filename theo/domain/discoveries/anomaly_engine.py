"""Anomaly detection engine that highlights atypical documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from sklearn.ensemble import IsolationForest

from .models import DocumentEmbedding


@dataclass(frozen=True)
class AnomalyDiscovery:
    """A candidate anomaly surfaced from the corpus."""

    document_id: str
    title: str
    description: str
    anomaly_score: float
    confidence: float
    relevance_score: float
    metadata: dict[str, object] = field(default_factory=dict)


class AnomalyDiscoveryEngine:
    """Detect atypical documents using an Isolation Forest model."""

    def __init__(
        self,
        *,
        contamination: float = 0.15,
        min_documents: int = 5,
        max_anomalies: int = 10,
        random_state: int | None = None,
        n_estimators: int = 200,
    ) -> None:
        self.contamination = max(1e-6, float(contamination))
        self.min_documents = max(2, int(min_documents))
        self.max_anomalies = max(1, int(max_anomalies))
        self.random_state = random_state
        self.n_estimators = max(50, int(n_estimators))

    def detect(self, documents: Sequence[DocumentEmbedding]) -> list[AnomalyDiscovery]:
        """Identify anomalous documents from *documents*."""

        filtered = [doc for doc in documents if doc.embedding]
        if len(filtered) < self.min_documents:
            return []

        embeddings = np.array([doc.embedding for doc in filtered], dtype=float)
        if embeddings.ndim != 2:
            embeddings = embeddings.reshape(len(filtered), -1)
        mask = np.isfinite(embeddings).all(axis=1)
        if not mask.all():
            filtered = [doc for doc, keep in zip(filtered, mask, strict=False) if keep]
            embeddings = embeddings[mask]
        if len(filtered) < self.min_documents:
            return []

        contamination = self._effective_contamination(len(filtered))
        forest = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=contamination,
            random_state=self.random_state,
        )
        forest.fit(embeddings)

        scores = forest.decision_function(embeddings)
        predictions = forest.predict(embeddings)
        anomaly_indices = [idx for idx, flag in enumerate(predictions) if flag == -1]
        if not anomaly_indices:
            return []

        severities = [max(0.0, -float(scores[idx])) for idx in anomaly_indices]
        max_severity = max(severities) if severities else 0.0
        if max_severity <= 0:
            max_severity = 1.0

        ordered_indices = sorted(anomaly_indices, key=lambda idx: scores[idx])
        discoveries: list[AnomalyDiscovery] = []
        for rank, idx in enumerate(ordered_indices, start=1):
            doc = filtered[idx]
            severity = max(0.0, -float(scores[idx]))
            normalised = severity / max_severity if max_severity else 0.0
            confidence = min(0.95, round(0.5 + 0.4 * normalised, 4))
            relevance = min(0.95, round(0.35 + 0.5 * normalised, 4))

            top_topics = [topic.strip() for topic in doc.topics if topic and topic.strip()][:3]
            topic_fragment = (
                f" focusing on {', '.join(top_topics)}" if top_topics else ""
            )
            description = (
                f"Document '{doc.title}' appears atypical compared to its peers"
                f"{topic_fragment}."
            )
            metadata = {
                "relatedDocuments": [doc.document_id],
                "relatedTopics": list(doc.topics),
                "anomalyData": {
                    "score": round(severity, 6),
                    "normalizedScore": round(normalised, 6),
                    "rank": rank,
                    "decisionFunction": round(float(scores[idx]), 6),
                },
            }
            discoveries.append(
                AnomalyDiscovery(
                    document_id=doc.document_id,
                    title=f"Atypical document: {doc.title}",
                    description=description.strip(),
                    anomaly_score=round(severity, 6),
                    confidence=confidence,
                    relevance_score=relevance,
                    metadata=metadata,
                )
            )
            if len(discoveries) >= self.max_anomalies:
                break

        return discoveries

    def _effective_contamination(self, document_count: int) -> float:
        ratio = max(1.0 / document_count, self.contamination)
        return min(0.5, ratio)


__all__ = ["AnomalyDiscovery", "AnomalyDiscoveryEngine"]
