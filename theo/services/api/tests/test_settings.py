"""Tests for Settings parsing helpers."""

from __future__ import annotations

import pytest

from theo.services.api.app.core.settings import Settings


@pytest.fixture(autouse=True)
def clear_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure environment variables do not interfere with parsing tests."""

    for key in (
        "THEO_API_KEYS",
        "API_KEYS",
        "THEO_AUTH_JWT_ALGORITHMS",
        "AUTH_JWT_ALGORITHMS",
        "THEO_CORS_ALLOWED_ORIGINS",
        "CORS_ALLOWED_ORIGINS",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("[\"key1\", \"key2\"]", ["key1", "key2"]),
        ("key1,key2", ["key1", "key2"]),
        ([" key1 ", "", "key2"], ["key1", "key2"]),
        (None, []),
    ],
)
def test_api_keys_parsing(value: object, expected: list[str]) -> None:
    payload = {"THEO_API_KEYS": value}
    settings = Settings.model_validate(payload)
    assert settings.api_keys == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("[\"hs256\", \"rs256\"]", ["HS256", "RS256"]),
        ("hs256,rs256", ["HS256", "RS256"]),
        (["hs256", "", "rs256"], ["HS256", "RS256"]),
        (None, ["HS256"]),
        ("", ["HS256"]),
    ],
)
def test_auth_jwt_algorithms_parsing(value: object, expected: list[str]) -> None:
    payload = {"THEO_AUTH_JWT_ALGORITHMS": value}
    settings = Settings.model_validate(payload)
    assert settings.auth_jwt_algorithms == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("[\"http://a\", \"http://b\"]", ["http://a", "http://b"]),
        ("http://a,http://b", ["http://a", "http://b"]),
        ([" http://a ", "", "http://b"], ["http://a", "http://b"]),
        (None, []),
    ],
)
def test_cors_origins_parsing(value: object, expected: list[str]) -> None:
    payload = {"THEO_CORS_ALLOWED_ORIGINS": value}
    settings = Settings.model_validate(payload)
    assert settings.cors_allowed_origins == expected


def test_auth_jwt_algorithms_default_uppercase() -> None:
    settings = Settings.model_validate({})
    assert settings.auth_jwt_algorithms == ["HS256"]
