"""Reranking helpers backed by a persisted joblib model."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import hashlib
import joblib  # type: ignore[import]

from ..models.search import HybridSearchResult
from .features import extract_features
from .mlflow_integration import (
    MlflowResolutionError,
    is_mlflow_uri,
    resolve_mlflow_artifact,
)


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RerankerValidationError(RuntimeError):
    """Raised when the persisted reranker fails validation prior to loading."""


def _load_model(path: Path, *, expected_sha256: str | None = None):
    if expected_sha256 is not None:
        actual_sha256 = _compute_sha256(path)
        if actual_sha256.lower() != expected_sha256.lower():
            raise RerankerValidationError(
                "Hash mismatch for reranker model: expected %s but loaded %s"
                % (expected_sha256, actual_sha256)
            )
    return joblib.load(path)


def _coerce_scores(raw: object) -> list[float]:
    if hasattr(raw, "tolist"):
        raw = raw.tolist()
    if isinstance(raw, (list, tuple)):
        if raw and isinstance(raw[0], (list, tuple)):
            return [float(row[-1]) for row in raw]
        return [float(value) for value in raw]
    return [float(raw)]


def _infer_positive_class_index(classes: Sequence[object]) -> int | None:
    """Best-effort inference of the "positive" class index.

    This favours numeric maxima, then semantic labels such as "relevant" or
    "positive". If no heuristic matches, ``None`` is returned so callers can
    fall back to alternative strategies.
    """

    if not classes:
        return None

    # Numeric classes – favour the highest value.
    if all(isinstance(entry, (int, float, bool)) for entry in classes):
        max_value = max(classes)
        try:
            return classes.index(max_value)
        except ValueError:
            return None

    # String-like labels – look for semantically "positive" names.
    def _normalise(label: object) -> str:
        text = str(label).lower()
        return "".join(ch for ch in text if ch.isalnum())

    positive_keywords = {"relevant", "positive", "true", "yes"}
    for index, label in enumerate(classes):
        if _normalise(label) in positive_keywords:
            return index

    return None


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
            classes: Sequence[object] | None = getattr(estimator, "classes_", None)
            class_list: list[object] | None = None
            positive_index: int | None = None
            if classes is not None:
                try:
                    class_list = list(classes)
                except TypeError:
                    class_list = None
            if class_list:
                positive_index = _infer_positive_class_index(class_list)
            predictions: Sequence[object] | None = None
            if (
                positive_index is None
                and class_list is not None
                and hasattr(estimator, "predict")
            ):
                raw_predictions = estimator.predict(feature_matrix)
                if hasattr(raw_predictions, "tolist"):
                    raw_predictions = raw_predictions.tolist()
                if isinstance(raw_predictions, Sequence):
                    predictions = raw_predictions
            scores: list[float] = []
            for index, row in enumerate(proba):
                if isinstance(row, (list, tuple)):
                    target_index: int | None = None
                    if positive_index is not None and positive_index < len(row):
                        target_index = positive_index
                    elif (
                        predictions is not None
                        and class_list is not None
                        and index < len(predictions)
                    ):
                        predicted_label = predictions[index]
                        try:
                            predicted_index = class_list.index(predicted_label)
                        except ValueError:
                            predicted_index = None
                        if predicted_index is not None and predicted_index < len(row):
                            target_index = predicted_index
                    if target_index is None or target_index >= len(row):
                        target_index = len(row) - 1
                    scores.append(float(row[target_index]))
                else:
                    scores.append(float(row))
            return scores
        if hasattr(estimator, "predict"):
            raw_scores = estimator.predict(feature_matrix)
            return _coerce_scores(raw_scores)
        raise TypeError("Estimator does not expose a supported scoring interface")

    def rerank(self, results: Sequence[HybridSearchResult]) -> list[HybridSearchResult]:
        """Return a new ordering of the supplied results sorted by the reranker."""

        results_list = list(results)
        scores = self.score(results_list)
        if not scores:
            return [item.model_copy(deep=True) for item in results_list]

        scored_indices = [
            (index, score) for index, score in enumerate(scores) if index < len(results_list)
        ]

        if not scored_indices:
            return [item.model_copy(deep=True) for item in results_list]

        ordered_indices = [
            index
            for index, _ in sorted(
                scored_indices,
                key=lambda item: item[1],
                reverse=True,
            )
        ]

        if len(ordered_indices) < len(results_list):
            covered = {index for index, _ in scored_indices}
            ordered_indices.extend(
                index for index in range(len(results_list)) if index not in covered
            )

        reranked: list[HybridSearchResult] = []
        for new_rank, index in enumerate(ordered_indices, start=1):
            source = results_list[index]
            clone = source.model_copy(deep=True)
            clone.rank = new_rank
            clone.score = scores[index] if index < len(scores) else source.score
            reranked.append(clone)
        return reranked


def load_reranker(
    path: str | Path, *, expected_sha256: str | None = None
) -> Reranker:
    """Load a reranker model from disk."""

    if is_mlflow_uri(path):
        try:
            artifact_path = resolve_mlflow_artifact(str(path))
        except MlflowResolutionError as exc:
            raise RerankerValidationError(str(exc)) from exc
        estimator = _load_model(artifact_path.resolve(), expected_sha256=expected_sha256)
    else:
        resolved = Path(path).resolve()
        estimator = _load_model(resolved, expected_sha256=expected_sha256)
    return Reranker(estimator)
