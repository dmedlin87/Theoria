"""Fallback reranker implementation used when scikit-learn is unavailable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass
class MinimalReranker:
    """Small linear model that approximates the gradient boosting pipeline.

    The model keeps a weight per feature column alongside a global bias and
    exposes a :meth:`predict` signature compatible with scikit-learn
    regressors. It is intentionally simple so it has no heavy dependencies and
    remains picklable across CLI invocations.
    """

    weights: List[float]
    bias: float

    def predict(self, rows: Iterable[Sequence[float]]) -> List[float]:
        predictions: List[float] = []
        for row in rows:
            score = self.bias
            for weight, value in zip(self.weights, row):
                score += weight * float(value)
            predictions.append(score)
        return predictions


def train_minimal_reranker(features: List[List[float]], labels: List[float]) -> MinimalReranker:
    label_sum = sum(labels)
    count = float(len(labels) or 1)
    bias = label_sum / count

    feature_count = len(features[0]) if features else 0
    weights = [0.0] * feature_count

    if feature_count:
        for row, label in zip(features, labels):
            for index, value in enumerate(row):
                weights[index] += float(value) * float(label)
        normaliser = float(len(labels)) or 1.0
        weights = [weight / normaliser for weight in weights]

    return MinimalReranker(weights=weights, bias=bias)

