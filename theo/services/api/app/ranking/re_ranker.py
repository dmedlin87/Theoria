"""Reranking helpers backed by a persisted joblib model."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Sequence

try:  # pragma: no cover - optional dependency
    import joblib  # type: ignore[import]
except Exception:  # pragma: no cover - gracefully handle missing joblib
    joblib = None  # type: ignore[assignment]

from ..models.search import HybridSearchResult
from .features import extract_features


def _load_model(path: Path):
    if joblib is not None:
        return joblib.load(path)
    with path.open("rb") as handle:
        return pickle.load(handle)


def _coerce_scores(raw: object) -> list[float]:
    if hasattr(raw, "tolist"):
        raw = raw.tolist()
    if isinstance(raw, (list, tuple)):
        if raw and isinstance(raw[0], (list, tuple)):
            return [float(row[-1]) for row in raw]
        return [float(value) for value in raw]
    return [float(raw)]


class Reranker:
    """Wrapper around a scikit-learn compatible estimator."""

    def __init__(self, estimator: object):
        self._estimator = estimator

    def score(self, results: Sequence[HybridSearchResult]) -> list[float]:
        """Return scores for each result using the underlying estimator."""

        feature_matrix = extract_features(results)
        if not feature_matrix:
            return []
        estimator = self._estimator
        if hasattr(estimator, "decision_function"):
            raw_scores = estimator.decision_function(feature_matrix)
            return _coerce_scores(raw_scores)
        if hasattr(estimator, "predict_proba"):
            proba = estimator.predict_proba(feature_matrix)
            if hasattr(proba, "tolist"):
                proba = proba.tolist()
            scores: list[float] = []
            for row in proba:
                if isinstance(row, (list, tuple)):
                    scores.append(float(row[-1]))
                else:
                    scores.append(float(row))
            return scores
        if hasattr(estimator, "predict"):
            raw_scores = estimator.predict(feature_matrix)
            return _coerce_scores(raw_scores)
        raise TypeError("Estimator does not expose a supported scoring interface")

    def rerank(self, results: Sequence[HybridSearchResult]) -> list[HybridSearchResult]:
        """Return a new ordering of the supplied results sorted by the reranker."""

        scores = self.score(results)
        if not scores:
            return list(results)
        paired = sorted(
            ((result, score) for result, score in zip(results, scores)),
            key=lambda item: item[1],
            reverse=True,
        )
        reranked: list[HybridSearchResult] = []
        for index, (result, score) in enumerate(paired, start=1):
            result.rank = index
            result.score = score
            reranked.append(result)
        return reranked


def load_reranker(path: str | Path) -> Reranker:
    """Load a reranker model from disk."""

    resolved = Path(path)
    estimator = _load_model(resolved)
    return Reranker(estimator)
