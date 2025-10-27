"""Feature extraction helpers for reranking search results."""

from __future__ import annotations

from typing import Sequence

from ..models.search import HybridSearchResult

FEATURE_NAMES: tuple[str, ...] = (
    "score",
    "vector_score",
    "lexical_score",
    "document_score",
    "document_rank",
    "rank",
    "osis_distance",
)


def _coerce(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def extract_features(results: Sequence[HybridSearchResult]) -> list[list[float]]:
    """Return a dense feature matrix for the supplied search results."""

    matrix: list[list[float]] = []
    for result in results:
        matrix.append(
            [
                _coerce(result.score),
                _coerce(result.vector_score),
                _coerce(result.lexical_score),
                _coerce(result.document_score),
                _coerce(result.document_rank),
                _coerce(result.rank),
                _coerce(result.osis_distance),
            ]
        )
    return matrix
