"""Tests for ranking metric helpers used by the API service."""

from __future__ import annotations

from theo.infrastructure.api.app.ranking import metrics


def test_ndcg_with_zero_k_returns_zero() -> None:
    ranked_ids = ["doc-1", "doc-2", "doc-3"]
    relevance = {"doc-1": 3.0, "doc-2": 2.0, "doc-3": 1.0}

    assert metrics.ndcg(ranked_ids, relevance, k=0) == 0.0


def test_ndcg_with_negative_k_returns_zero() -> None:
    ranked_ids = ["doc-1", "doc-2", "doc-3"]
    relevance = {"doc-1": 3.0, "doc-2": 2.0, "doc-3": 1.0}

    assert metrics.ndcg(ranked_ids, relevance, k=-5) == 0.0
