"""Unit tests for :mod:`theo.services.api.app.ai.memory_index`."""

from theo.services.api.app.ai.memory_index import MemoryIndex


def test_score_similarity_identical_vectors() -> None:
    index = MemoryIndex()
    embedding = [1.0, 2.0, 3.0]

    result = index.score_similarity(embedding, embedding)

    assert result == 1.0


def test_score_similarity_orthogonal_vectors() -> None:
    index = MemoryIndex()

    result = index.score_similarity([1.0, 0.0], [0.0, 1.0])

    assert result == 0.0


def test_score_similarity_mismatched_lengths() -> None:
    index = MemoryIndex()

    result = index.score_similarity([1.0], [1.0, 0.0])

    assert result is None
