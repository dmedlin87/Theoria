"""Tests for the lightweight MinimalReranker fallback implementation."""

from __future__ import annotations

import pytest

from ranking.minimal_reranker import MinimalReranker, train_minimal_reranker


def test_predict_applies_bias_and_weights() -> None:
    model = MinimalReranker(weights=[0.5, -0.25], bias=0.2)

    scores = model.predict([(2, 4), (0, -4), (1.5, 0)])

    assert scores == pytest.approx([0.2, 1.2, 0.95])


def test_training_computes_average_bias_and_weight_estimates() -> None:
    features = [
        [1.0, 0.0],
        [0.0, 2.0],
        [0.5, 0.5],
    ]
    labels = [1.0, 2.0, 3.0]

    model = train_minimal_reranker(features, labels)

    expected_bias = sum(labels) / len(labels)
    expected_weights = [
        (1.0 * 1.0 + 0.0 * 2.0 + 0.5 * 3.0) / len(labels),
        (0.0 * 1.0 + 2.0 * 2.0 + 0.5 * 3.0) / len(labels),
    ]
    assert model.bias == pytest.approx(expected_bias)
    assert model.weights == pytest.approx(expected_weights)


def test_training_handles_empty_datasets() -> None:
    model = train_minimal_reranker([], [])

    assert model.bias == 0.0
    assert model.weights == []
    assert model.predict([[]]) == pytest.approx([0.0])

