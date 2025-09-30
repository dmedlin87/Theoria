"""Ranking metric helpers used by training and evaluation scripts."""

from __future__ import annotations

import math
from typing import Iterable, Sequence


def _validate_relevances(relevances: Sequence[float]) -> None:
    if not isinstance(relevances, Sequence):
        raise TypeError("relevances must be a sequence of floats")


def dcg_at_k(relevances: Sequence[float], k: int) -> float:
    """Return the discounted cumulative gain for the first *k* items."""

    _validate_relevances(relevances)
    if k <= 0:
        return 0.0

    score = 0.0
    for index, relevance in enumerate(relevances[:k]):
        if relevance <= 0:
            continue
        # index is zero-based; add 2 inside the log to get ranks starting at 1.
        score += float(relevance) / math.log2(index + 2.0)
    return score


def ndcg_at_k(relevances: Sequence[float], k: int) -> float:
    """Return the normalised discounted cumulative gain for the first *k* items."""

    _validate_relevances(relevances)
    ideal = dcg_at_k(sorted(relevances, reverse=True), k)
    if ideal == 0:
        return 0.0
    return dcg_at_k(relevances, k) / ideal


def mean_reciprocal_rank(relevances: Sequence[float]) -> float:
    """Return the reciprocal rank of the first relevant item in *relevances*."""

    _validate_relevances(relevances)
    for index, relevance in enumerate(relevances):
        if relevance > 0:
            return 1.0 / float(index + 1)
    return 0.0


def recall_at_k(relevances: Sequence[float], k: int) -> float:
    """Return recall@k for binary or graded relevance labels."""

    _validate_relevances(relevances)
    if k <= 0:
        return 0.0

    total_relevant = sum(1 for relevance in relevances if relevance > 0)
    if total_relevant == 0:
        return 0.0

    retrieved_relevant = sum(1 for relevance in relevances[:k] if relevance > 0)
    return retrieved_relevant / float(total_relevant)


def batch_ndcg_at_k(rankings: Iterable[Sequence[float]], k: int) -> float:
    """Return the mean nDCG@k across *rankings*."""

    rankings = list(rankings)
    if not rankings:
        return 0.0
    return sum(ndcg_at_k(ranking, k) for ranking in rankings) / float(len(rankings))


def batch_mrr(rankings: Iterable[Sequence[float]]) -> float:
    """Return the mean reciprocal rank across *rankings*."""

    rankings = list(rankings)
    if not rankings:
        return 0.0
    return sum(mean_reciprocal_rank(ranking) for ranking in rankings) / float(len(rankings))


def batch_recall_at_k(rankings: Iterable[Sequence[float]], k: int) -> float:
    """Return the mean recall@k across *rankings*."""

    rankings = list(rankings)
    if not rankings:
        return 0.0
    return sum(recall_at_k(ranking, k) for ranking in rankings) / float(len(rankings))

