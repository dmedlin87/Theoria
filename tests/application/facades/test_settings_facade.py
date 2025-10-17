import base64
from pathlib import Path
from cryptography.fernet import Fernet

import pytest

from theo.application.facades import settings as settings_module
from theo.application.facades.runtime import allow_insecure_startup
from theo.application.ports.secrets import SecretRequest


@pytest.fixture(autouse=True)
def reset_settings_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure settings caches and relevant environment variables are isolated."""

    for variable in (
        "SETTINGS_SECRET_KEY",
        "SETTINGS_SECRET_BACKEND",
        "THEO_SETTINGS_SECRET_BACKEND",
        "SETTINGS_SECRET_NAME",
        "THEO_SETTINGS_SECRET_NAME",
        "SETTINGS_SECRET_FIELD",
        "THEO_SETTINGS_SECRET_FIELD",
        "SECRETS_VAULT_ADDR",
        "THEO_SECRETS_VAULT_ADDR",
        "SECRETS_VAULT_TOKEN",
        "THEO_SECRETS_VAULT_TOKEN",
        "SECRETS_VAULT_NAMESPACE",
        "THEO_SECRETS_VAULT_NAMESPACE",
        "SECRETS_VAULT_MOUNT_POINT",
        "THEO_SECRETS_VAULT_MOUNT_POINT",
        "SECRETS_VAULT_VERIFY",
        "THEO_SECRETS_VAULT_VERIFY",
        "SECRETS_AWS_PROFILE",
        "THEO_SECRETS_AWS_PROFILE",
        "SECRETS_AWS_REGION",
        "THEO_SECRETS_AWS_REGION",
        "THEO_ALLOW_INSECURE_STARTUP",
        "THEORIA_ENVIRONMENT",
        "THEO_ENVIRONMENT",
        "ENVIRONMENT",
        "THEORIA_PROFILE",
    ):
        monkeypatch.delenv(variable, raising=False)

    settings_module.get_settings.cache_clear()
    settings_module.get_settings_secret.cache_clear()
    settings_module.get_settings_cipher.cache_clear()
    allow_insecure_startup.cache_clear()

    yield

    settings_module.get_settings.cache_clear()
    settings_module.get_settings_secret.cache_clear()
    settings_module.get_settings_cipher.cache_clear()
    allow_insecure_startup.cache_clear()


def test_derive_fernet_key_is_deterministic() -> None:
    first = settings_module._derive_fernet_key("super-secret")
    second = settings_module._derive_fernet_key("super-secret")

    assert first == second
    assert isinstance(first, bytes)
    # SHA256 produces 32 bytes; urlsafe base64 encoding yields 44 characters
    assert len(first) == 44
    # Encoded value should round-trip through base64 decoding without padding errors
    assert base64.urlsafe_b64decode(first) == base64.urlsafe_b64decode(second)


@pytest.mark.parametrize(
    ("value", "kwargs", "expected"),
    [
        ("alpha, beta,, gamma", {}, ["alpha", "beta", "gamma"]),
        (
            '["One", "Two", " "]',
            {"transform": lambda item: item.upper()},
            ["ONE", "TWO"],
        ),
        (["first", "", "second"], {}, ["first", "second"]),
        (None, {"default": ["fallback"]}, ["fallback"]),
        ("  \n  ", {"default": ["fallback"]}, ["fallback"]),
    ],
)
def test_parse_json_or_comma_collection_handles_variants(
    value: object, kwargs: dict[str, object], expected: list[str]
) -> None:
    result = settings_module.Settings._parse_json_or_comma_collection(value, **kwargs)

    assert result == expected


def test_parse_json_or_comma_collection_invalid_type_raises() -> None:
    with pytest.raises(ValueError):
        settings_module.Settings._parse_json_or_comma_collection(42)


def test_parse_string_collection_normalises_iterables() -> None:
    """String collections accept varied iterable inputs."""

    result_from_string = settings_module.Settings._parse_string_collection(
        "alpha, beta , , gamma"
    )
    assert result_from_string == ["alpha", "beta", "gamma"]

    result_from_tuple = settings_module.Settings._parse_string_collection(
        (" first ", "second", "")
    )
    assert result_from_tuple == ["first", "second"]

    result_from_set = settings_module.Settings._parse_string_collection(
        {"gamma", "delta", "  epsilon  "}
    )
    assert set(result_from_set) == {"gamma", "delta", "epsilon"}


def test_parse_string_collection_invalid_type_raises() -> None:
    with pytest.raises(ValueError):
        settings_module.Settings._parse_string_collection(42)


def test_get_settings_cipher_uses_configured_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SETTINGS_SECRET_KEY", "application-secret")

    cipher = settings_module.get_settings_cipher()

    assert cipher is not None
    token = cipher.encrypt(b"theoria")
    mirror = Fernet(settings_module._derive_fernet_key("application-secret"))
    assert mirror.decrypt(token) == b"theoria"


def test_get_settings_cipher_uses_secrets_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[SecretRequest] = []

    class DummyAdapter:
        def get_secret(self, request: SecretRequest) -> str:
            calls.append(request)
            return "remote-secret"

    monkeypatch.setenv("SETTINGS_SECRET_BACKEND", "vault")
    monkeypatch.setenv("SETTINGS_SECRET_NAME", "theoria/app")
    monkeypatch.setattr(
        settings_module,
        "build_secrets_adapter",
        lambda backend, **kwargs: DummyAdapter(),
    )

    cipher = settings_module.get_settings_cipher()

    assert cipher is not None
    assert calls and calls[0].identifier == "theoria/app"
    token = cipher.encrypt(b"secret")
    mirror = Fernet(settings_module._derive_fernet_key("remote-secret"))
    assert mirror.decrypt(token) == b"secret"


def test_get_settings_cipher_returns_none_without_secret() -> None:
    cipher = settings_module.get_settings_cipher()

    assert cipher is None


def test_get_settings_cipher_uses_insecure_fallback_when_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("THEO_ALLOW_INSECURE_STARTUP", "true")
    monkeypatch.setenv("THEORIA_ENVIRONMENT", "development")
    allow_insecure_startup.cache_clear()

    cipher = settings_module.get_settings_cipher()

    assert cipher is not None
    token = cipher.encrypt(b"theoria")
    fallback_key = settings_module._derive_fernet_key("theoria-insecure-test-secret")
    mirror = Fernet(fallback_key)
    assert mirror.decrypt(token) == b"theoria"


def test_get_settings_cipher_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SETTINGS_SECRET_KEY", "cache-secret")
    call_count = 0

    class DummyFernet:
        def __init__(self, key: bytes) -> None:
            nonlocal call_count
            call_count += 1
            self.key = key

        def encrypt(self, payload: bytes) -> bytes:  # pragma: no cover - not exercised
            return payload

        def decrypt(self, payload: bytes) -> bytes:  # pragma: no cover - not exercised
            return payload

    monkeypatch.setattr(settings_module, "Fernet", DummyFernet)

    first = settings_module.get_settings_cipher()
    second = settings_module.get_settings_cipher()

    assert first is second
    assert first.key == settings_module._derive_fernet_key("cache-secret")
    assert call_count == 1


def test_has_auth_jwt_credentials_detects_multiple_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Any configured secret or key source should enable credentials."""

    monkeypatch.setenv("AUTH_JWT_SECRET", "super-secret")
    from_env_secret = settings_module.Settings()
    assert from_env_secret.has_auth_jwt_credentials() is True

    monkeypatch.delenv("AUTH_JWT_SECRET", raising=False)

    monkeypatch.setenv("AUTH_JWT_PUBLIC_KEY", "  KEY  ")
    inline_key = settings_module.Settings()
    assert inline_key.has_auth_jwt_credentials() is True

    monkeypatch.delenv("AUTH_JWT_PUBLIC_KEY", raising=False)

    key_dir = tmp_path / "jwt"
    key_dir.mkdir()
    key_path = key_dir / "public.pem"
    key_path.write_text("JWT KEY", encoding="utf-8")
    monkeypatch.setenv("AUTH_JWT_PUBLIC_KEY_PATH", str(key_path))
    from_path = settings_module.Settings()
    assert from_path.has_auth_jwt_credentials() is True


def test_has_auth_jwt_credentials_returns_false_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no credentials are configured the helper should return False."""

    for variable in [
        "AUTH_JWT_SECRET",
        "AUTH_JWT_PUBLIC_KEY",
        "AUTH_JWT_PUBLIC_KEY_PATH",
        "THEO_AUTH_JWT_SECRET",
        "THEO_AUTH_JWT_PUBLIC_KEY",
        "THEO_AUTH_JWT_PUBLIC_KEY_PATH",
    ]:
        monkeypatch.delenv(variable, raising=False)

    empty = settings_module.Settings()
    assert empty.has_auth_jwt_credentials() is False
