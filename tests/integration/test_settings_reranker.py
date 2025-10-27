from __future__ import annotations

from pathlib import Path

import pytest

from theo.application.facades.settings import Settings, get_settings


def test_settings_reranker_validation_across_envs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Load settings from environment variables and validate reranker constraints."""

    storage_root = tmp_path / "storage"
    reranker_root = storage_root / "rerankers"
    reranker_root.mkdir(parents=True)

    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("RERANKER_ENABLED", "true")
    monkeypatch.setenv("RERANKER_MODEL_PATH", "model.joblib")
    monkeypatch.setenv("RERANKER_MODEL_SHA256", "a" * 64)

    settings = Settings()
    expected_path = (reranker_root / "model.joblib").resolve()
    assert settings.reranker_model_path == expected_path

    monkeypatch.setenv("RERANKER_MODEL_SHA256", "invalid")
    get_settings.cache_clear()
    with pytest.raises(ValueError):
        Settings()
