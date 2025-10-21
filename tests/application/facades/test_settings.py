from pathlib import Path

import pytest

from theo.application.facades import runtime as runtime_module
from theo.application.facades import settings as settings_module
from theo.application.facades.settings import Settings


@pytest.fixture(autouse=True)
def _clear_settings_caches():
    settings_module.get_settings.cache_clear()
    settings_module.get_settings_secret.cache_clear()
    settings_module.get_settings_cipher.cache_clear()
    runtime_module.allow_insecure_startup.cache_clear()
    yield
    settings_module.get_settings.cache_clear()
    settings_module.get_settings_secret.cache_clear()
    settings_module.get_settings_cipher.cache_clear()
    runtime_module.allow_insecure_startup.cache_clear()


def test_settings_collection_parsers():
    assert Settings._parse_api_keys('["alpha", "beta"]') == ["alpha", "beta"]
    assert Settings._parse_algorithms("rs256,HS256") == ["RS256", "HS256"]
    assert Settings._parse_cors_origins(
        ["https://example.com", "https://theoria.ai"]
    ) == ["https://example.com", "https://theoria.ai"]


def test_reranker_configuration_normalizes_paths(tmp_path: Path):
    digest = "ABCDEF" * 10 + "ABCD"
    storage_root = tmp_path / "storage"
    storage_root.mkdir()

    settings = Settings(
        reranker_enabled=True,
        storage_root=storage_root,
        reranker_model_path=Path("model.bin"),
        reranker_model_sha256=digest,
    )

    expected_path = (storage_root / "rerankers" / "model.bin").resolve()
    assert settings.reranker_model_path == expected_path
    assert settings.reranker_model_sha256 == digest.lower()


def test_reranker_configuration_rejects_external_paths(tmp_path: Path):
    digest = "1" * 64
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    with pytest.raises(ValueError):
        Settings(
            reranker_enabled=True,
            storage_root=storage_root,
            reranker_model_path=storage_root.parent / "other.bin",
            reranker_model_sha256=digest,
        )


def test_get_settings_cipher_uses_insecure_fallback(monkeypatch):
    monkeypatch.setenv("THEO_ALLOW_INSECURE_STARTUP", "1")
    monkeypatch.setenv("THEORIA_ENVIRONMENT", "development")
    monkeypatch.delenv("SETTINGS_SECRET_KEY", raising=False)
    monkeypatch.delenv("THEO_SETTINGS_SECRET_KEY", raising=False)

    cipher_one = settings_module.get_settings_cipher()
    assert cipher_one is not None
    cipher_two = settings_module.get_settings_cipher()
    assert cipher_one is cipher_two

    payload = cipher_one.encrypt(b"theoria")
    assert cipher_one.decrypt(payload) == b"theoria"
