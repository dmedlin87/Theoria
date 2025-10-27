"""Unit tests for retrieval service helper utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from theo.application.facades.settings import Settings
from theo.infrastructure.api.app.infra.retrieval_service import (
    _RerankerCache,
    _format_reranker_header,
    _iter_reranker_references,
)


@pytest.mark.parametrize(
    "reference, expected",
    [
        ("models:/theo/reranker@Production/some/path", "Production"),
        ("models:/theo/reranker/Production", "Production"),
        ("runs:/1234abcd/artifacts/model.joblib", "model.joblib"),
        ("/models/reranker.bin", "reranker.bin"),
        (None, None),
    ],
)
def test_format_reranker_header_handles_various_inputs(
    reference: str | None, expected: str | None
) -> None:
    """Ensure human readable reranker headers are generated consistently."""

    assert _format_reranker_header(reference) == expected


def test_iter_reranker_references_prioritises_registry_then_files() -> None:
    settings = Settings()
    settings.reranker_model_registry_uri = "models:/theo/reranker@Production"
    settings.reranker_model_path = "/path/to/model.bin"
    settings.reranker_model_sha256 = "abc123"

    references = _iter_reranker_references(settings)

    assert references == [
        ("models:/theo/reranker@Production", None),
        ("/path/to/model.bin", "abc123"),
    ]


def test_reranker_cache_returns_cached_instance(tmp_path: Path) -> None:
    created: list[tuple[str, str | None]] = []

    def loader(model_path: str, expected_sha256: str | None) -> dict[str, str | None]:
        created.append((model_path, expected_sha256))
        return {"path": model_path, "sha256": expected_sha256}

    cache = _RerankerCache(loader=loader)

    model_file = tmp_path / "model.joblib"
    model_file.write_bytes(b"contents")

    first = cache.resolve(model_file, "digest-1")
    second = cache.resolve(model_file, "digest-1")

    assert first == {"path": str(model_file), "sha256": "digest-1"}
    assert second is first
    assert created == [(str(model_file), "digest-1")]


def test_reranker_cache_resets_after_path_change(tmp_path: Path) -> None:
    created: list[str] = []

    def loader(model_path: str, expected_sha256: str | None) -> str:
        created.append(model_path)
        return model_path

    cache = _RerankerCache(loader=loader)

    first_model = tmp_path / "model_a.joblib"
    first_model.write_bytes(b"a")
    second_model = tmp_path / "model_b.joblib"
    second_model.write_bytes(b"b")

    first = cache.resolve(first_model, None)
    second = cache.resolve(second_model, None)

    assert first == str(first_model)
    assert second == str(second_model)
    assert created == [str(first_model), str(second_model)]


def test_reranker_cache_resets_failure_after_artifact_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts: list[str] = []
    loader_state = {"raise": True}

    def loader(model_path: str, expected_sha256: str | None) -> str:
        attempts.append(model_path)
        if loader_state["raise"]:
            raise RuntimeError("load failed")
        return model_path

    cache = _RerankerCache(loader=loader)
    model_file = tmp_path / "model.joblib"
    model_file.write_bytes(b"initial")

    # First attempt fails and is cached as a failure.
    assert cache.resolve(model_file, None) is None
    assert cache.failed is True
    assert attempts == [str(model_file)]

    # Simulate artifact change by bumping timestamp and disabling failure.
    loader_state["raise"] = False
    monkeypatch.setattr(
        "theo.infrastructure.api.app.infra.retrieval_service._RerankerCache._snapshot_artifact",
        staticmethod(lambda path: ("new", 1)),
    )
    cache.failed = True
    cache._artifact_signature = ("old", 0)

    resolved = cache.resolve(model_file, None)

    assert resolved == str(model_file)
    assert attempts == [str(model_file), str(model_file)]
