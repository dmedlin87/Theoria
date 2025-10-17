import pytest

from ranking import metrics


def test_ndcg_at_k_matches_reference():
    relevances = [3, 2, 3, 0, 1, 2]
    result = metrics.ndcg_at_k(relevances, k=6)
    # Reference value from the canonical nDCG example.
    assert result == pytest.approx(0.961, rel=1e-3)


def test_mean_reciprocal_rank_handles_no_relevance():
    assert metrics.mean_reciprocal_rank([0, 0, 0]) == 0.0
    assert metrics.mean_reciprocal_rank([0, 1, 0]) == pytest.approx(0.5)


def test_recall_at_k_binary_labels():
    relevances = [1, 0, 1, 0]
    assert metrics.recall_at_k(relevances, k=1) == 0.5
    assert metrics.recall_at_k(relevances, k=3) == 1.0


def test_recall_at_k_handles_edge_cases():
    assert metrics.recall_at_k([0, 0, 0], k=2) == 0.0
    assert metrics.recall_at_k([1, 0, 1], k=0) == 0.0


def test_batch_metrics_average_sequences():
    rankings = [[1, 0, 0], [0, 1, 0]]
    assert metrics.batch_ndcg_at_k(rankings, 3) == pytest.approx(
        (metrics.ndcg_at_k(rankings[0], 3) + metrics.ndcg_at_k(rankings[1], 3)) / 2
    )
    assert metrics.batch_mrr(rankings) == pytest.approx(
        (metrics.mean_reciprocal_rank(rankings[0]) + metrics.mean_reciprocal_rank(rankings[1])) / 2
    )
    assert metrics.batch_recall_at_k(rankings, 3) == pytest.approx(
        (metrics.recall_at_k(rankings[0], 3) + metrics.recall_at_k(rankings[1], 3)) / 2
    )


def test_dcg_and_ndcg_cover_additional_branches():
    assert metrics.dcg_at_k([3, -1, 2], k=0) == 0.0
    assert metrics.ndcg_at_k([0, 0, 0], k=5) == 0.0


def test_batch_metrics_handle_empty_sequences():
    assert metrics.batch_ndcg_at_k([], 5) == 0.0
    assert metrics.batch_mrr([]) == 0.0
    assert metrics.batch_recall_at_k([], 5) == 0.0


def test_metric_functions_validate_input_types():
    with pytest.raises(TypeError):
        metrics.dcg_at_k(None, 3)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        metrics.ndcg_at_k(None, 3)  # type: ignore[arg-type]

