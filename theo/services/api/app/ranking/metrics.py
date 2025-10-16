"""Ranking quality metrics."""

from __future__ import annotations

import math
from typing import Mapping, Sequence


def dcg(relevances: Sequence[float]) -> float:
    """Compute Discounted Cumulative Gain for a ranked list."""

    score = 0.0
    for index, relevance in enumerate(relevances, start=1):
        if relevance <= 0:
            continue
        score += float(relevance) / math.log2(index + 1)
    return score


def ndcg(
    ranked_ids: Sequence[str],
    relevance: Mapping[str, float],
    *,
    k: int | None = None,
) -> float:
    """Compute Normalized Discounted Cumulative Gain for ranked identifiers."""

    if k is None:
        limit = len(ranked_ids)
    else:
        if k <= 0:
            return 0.0
        limit = k
    observed = [float(relevance.get(item, 0.0)) for item in ranked_ids[:limit]]
    ideal = sorted((float(value) for value in relevance.values()), reverse=True)[:limit]
    ideal_dcg = dcg(ideal)
    if ideal_dcg == 0.0:
        return 0.0
    return dcg(observed) / ideal_dcg


def mrr(ranked_ids: Sequence[str], relevant_ids: Sequence[str]) -> float:
    """Compute the Mean Reciprocal Rank for the supplied ordering."""

    relevant_set = {item for item in relevant_ids}
    for index, identifier in enumerate(ranked_ids, start=1):
        if identifier in relevant_set:
            return 1.0 / index
    return 0.0
