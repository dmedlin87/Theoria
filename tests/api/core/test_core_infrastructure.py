"""Regression coverage for the application facade layer."""
from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass
from typing import Any, Iterable

import pytest
from sqlalchemy import text


@dataclass
class MemoryAppSetting:
    """Minimal in-memory representation of ``AppSetting`` records."""

    key: str
    value: Any


class MemorySession:
    """SessionProtocol stub persisting settings in memory for tests."""

    def __init__(self, initial: Iterable[MemoryAppSetting] | None = None) -> None:
        self.storage: dict[str, MemoryAppSetting] = {}
        if initial is not None:
            for record in initial:
                self.storage[record.key] = record
        self.commits = 0

    def get(self, _model: Any, key: str) -> MemoryAppSetting | None:  # noqa: D401
        """Return the setting record for the given key, or None if not found."""
        return self.storage.get(key)

    def add(self, record: MemoryAppSetting) -> None:
        self.storage[record.key] = record

    def commit(self) -> None:
        self.commits += 1


FACADE_DEFINITIONS = [
    {
        "module": "theo.application.facades.database",
        "exports": ["Base", "configure_engine", "get_engine", "get_session"],
        "callables": ["configure_engine", "get_engine", "get_session"],
    },
    {
        "module": "theo.application.facades.runtime",
        "exports": ["allow_insecure_startup", "current_runtime_environment"],
        "callables": ["allow_insecure_startup", "current_runtime_environment"],
    },
    {
        "module": "theo.application.facades.secret_migration",
        "exports": ["migrate_secret_settings"],
        "callables": ["migrate_secret_settings"],
    },
    {
        "module": "theo.application.facades.settings",
        "exports": ["Settings", "get_settings", "get_settings_cipher"],
        "callables": ["get_settings", "get_settings_cipher"],
    },
    {
        "module": "theo.application.facades.settings_store",
        "exports": [
            "SETTINGS_NAMESPACE",
            "SettingNotFoundError",
            "load_setting",
            "require_setting",
            "save_setting",
        ],
        "callables": ["load_setting", "require_setting", "save_setting"],
    },
    {
        "module": "theo.application.facades.version",
        "exports": ["get_git_sha"],
        "callables": ["get_git_sha"],
    },
]


def _import_module(name: str):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


@pytest.mark.parametrize("definition", FACADE_DEFINITIONS)
def test_facade_exports_are_available(definition: dict[str, Any]) -> None:
    module = _import_module(definition["module"])
    exported_names = set(definition["exports"])
    module_exports = set(getattr(module, "__all__", exported_names))
    assert exported_names.issubset(module_exports)

    for export in definition["exports"]:
        assert hasattr(module, export)


ALL_CALLABLE_EXPORTS = sorted(
    {name for definition in FACADE_DEFINITIONS for name in definition["callables"]}
)


@pytest.mark.parametrize("definition", FACADE_DEFINITIONS)
@pytest.mark.parametrize("callable_name", ALL_CALLABLE_EXPORTS)
def test_facade_callables_are_callable(
    definition: dict[str, Any], callable_name: str
) -> None:
    module = _import_module(definition["module"])
    attribute = getattr(module, callable_name, None)
    if callable_name not in definition["callables"]:
        pytest.skip("Callable not exported by this facade")
    assert callable(attribute)


def test_runtime_allow_insecure_startup_respects_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_module = _import_module("theo.application.facades.runtime")
    runtime_module.allow_insecure_startup.cache_clear()

    monkeypatch.setenv("THEO_ALLOW_INSECURE_STARTUP", "true")
    monkeypatch.setenv("THEORIA_ENVIRONMENT", "development")
    assert runtime_module.allow_insecure_startup() is True

    runtime_module.allow_insecure_startup.cache_clear()
    monkeypatch.setenv("THEORIA_ENVIRONMENT", "production")
    with pytest.raises(RuntimeError):
        runtime_module.allow_insecure_startup()

    runtime_module.allow_insecure_startup.cache_clear()


def test_database_connection_helpers_create_sessions() -> None:
    database_module = _import_module("theo.application.facades.database")
    engine = database_module.configure_engine("sqlite:///:memory:")
    try:
        assert str(engine.url) == "sqlite:///:memory:"
        assert database_module.get_engine() is engine

        session_gen = database_module.get_session()
        session = next(session_gen)
        try:
            result = session.execute(text("SELECT 1")).scalar_one()
            assert result == 1
        finally:
            session_gen.close()
    finally:
        engine.dispose()
        setattr(database_module, "_engine", None)
        setattr(database_module, "_SessionLocal", None)
        setattr(database_module, "_engine_url_override", None)


class FakeCipher:
    """Deterministic cipher used to exercise encryption flows."""

    def __init__(self) -> None:
        self.encrypted: list[str] = []

    def encrypt(self, payload: bytes) -> bytes:
        token = f"enc:{payload.decode('utf-8')}"
        self.encrypted.append(token)
        return token.encode("utf-8")

    def decrypt(self, token: bytes) -> bytes:
        token_str = token.decode("utf-8")
        assert token_str.startswith("enc:")
        return token_str[len("enc:") :].encode("utf-8")


def _patch_app_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    facade_store = importlib.import_module("theo.application.facades.settings_store")
    monkeypatch.setattr(facade_store, "AppSetting", MemoryAppSetting)


def test_settings_store_encryption_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_app_setting(monkeypatch)
    facade_store = importlib.import_module("theo.application.facades.settings_store")
    cipher = FakeCipher()
    monkeypatch.setattr(facade_store, "get_settings_cipher", lambda: cipher)

    session = MemorySession()
    facade_store.save_setting(session, "provider.credentials", {"api_key": "secret"})
    qualified = f"{facade_store.SETTINGS_NAMESPACE}:provider.credentials"
    record = session.storage[qualified]
    assert isinstance(record.value, dict)
    assert "__encrypted__" in record.value

    loaded = facade_store.load_setting(session, "provider.credentials")
    assert loaded == {"api_key": "secret"}

    required = facade_store.require_setting(session, "provider.credentials")
    assert required == {"api_key": "secret"}
    assert session.commits == 1


def test_settings_store_requires_cipher_for_sensitive_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_app_setting(monkeypatch)
    facade_store = importlib.import_module("theo.application.facades.settings_store")
    monkeypatch.setattr(facade_store, "get_settings_cipher", lambda: None)

    session = MemorySession()
    with pytest.raises(RuntimeError):
        facade_store.save_setting(session, "provider.credentials", {"api_key": "secret"})

    encrypted_record = MemoryAppSetting(
        key=f"{facade_store.SETTINGS_NAMESPACE}:provider.credentials",
        value={"__encrypted__": "enc:payload"},
    )
    session.storage[encrypted_record.key] = encrypted_record
    with pytest.raises(RuntimeError):
        facade_store.load_setting(session, "provider.credentials")


def test_secret_migration_encrypts_plaintext_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_app_setting(monkeypatch)
    facade_store = importlib.import_module("theo.application.facades.settings_store")
    facade_secret = importlib.import_module("theo.application.facades.secret_migration")

    cipher = FakeCipher()
    monkeypatch.setattr(facade_store, "get_settings_cipher", lambda: cipher)
    monkeypatch.setattr(facade_secret, "get_settings_cipher", lambda: cipher)

    monkeypatch.setattr(
        facade_secret,
        "registry_from_payload",
        lambda payload: (payload or {}, []),
    )

    captured_registries: list[Any] = []

    def _registry_saver(session: MemorySession, registry: Any) -> None:
        captured_registries.append(registry)
        facade_store.save_setting(session, "llm", registry)

    facade_secret.set_llm_registry_saver(_registry_saver)

    llm_key = f"{facade_store.SETTINGS_NAMESPACE}:llm"
    provider_key = f"{facade_store.SETTINGS_NAMESPACE}:ai_providers"
    session = MemorySession(
        [
            MemoryAppSetting(
                key=llm_key,
                value={
                    "models": [
                        {
                            "name": "gpt",
                            "config": {"api_key": "top-secret"},
                        }
                    ]
                },
            ),
            MemoryAppSetting(
                key=provider_key,
                value={"openai": {"api_key": "plaintext"}},
            ),
        ]
    )

    migrated = facade_secret.migrate_secret_settings(session)
    assert migrated == ["llm", "ai_providers"]
    assert captured_registries == [
        {
            "models": [
                {
                    "name": "gpt",
                    "config": {"api_key": "top-secret"},
                }
            ]
        }
    ]
    assert "__encrypted__" in session.storage[provider_key].value

    migrated_again = facade_secret.migrate_secret_settings(session)
    assert migrated_again == []

    facade_secret.set_llm_registry_saver(lambda *_args, **_kwargs: None)


def test_settings_secret_resolution_uses_configured_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade_settings = importlib.reload(
        importlib.import_module("theo.application.facades.settings")
    )

    facade_settings.get_settings.cache_clear()
    facade_settings.get_settings_secret.cache_clear()
    facade_settings.get_settings_cipher.cache_clear()

    class FakeAdapter:
        def __init__(self) -> None:
            self.requests: list[Any] = []

        def get_secret(self, request: Any) -> str:
            self.requests.append(request)
            return "backend-secret"

    fake_adapter = FakeAdapter()

    def fake_build(backend: str, **kwargs: Any) -> FakeAdapter:
        assert backend == "vault"
        fake_adapter.config = kwargs
        return fake_adapter

    monkeypatch.setenv("SETTINGS_SECRET_BACKEND", "vault")
    monkeypatch.setenv("SETTINGS_SECRET_NAME", "theoria/settings")
    monkeypatch.setenv("SETTINGS_SECRET_FIELD", "token")
    monkeypatch.setenv("SECRETS_VAULT_ADDR", "http://vault")
    monkeypatch.setenv("SECRETS_VAULT_TOKEN", "vault-token")
    monkeypatch.setenv("THEO_CORS_ALLOWED_ORIGINS", "[\"https://example.com\"]")

    monkeypatch.setattr(facade_settings, "build_secrets_adapter", fake_build)
    monkeypatch.setattr(facade_settings, "allow_insecure_startup", lambda: False)

    class FakeFernet:
        def __init__(self, key: bytes) -> None:
            self.key = key

    monkeypatch.setattr(facade_settings, "Fernet", FakeFernet)

    secret = facade_settings.get_settings_secret()
    assert secret == "backend-secret"
    cipher = facade_settings.get_settings_cipher()
    assert isinstance(cipher, FakeFernet)
    assert fake_adapter.requests and fake_adapter.requests[0].identifier == "theoria/settings"

    settings_obj = facade_settings.get_settings()
    assert settings_obj.cors_allowed_origins == ["https://example.com"]

    facade_settings.get_settings.cache_clear()
    facade_settings.get_settings_secret.cache_clear()
    facade_settings.get_settings_cipher.cache_clear()


def test_version_get_git_sha_invokes_git_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    facade_version = importlib.reload(
        importlib.import_module("theo.application.facades.version")
    )

    facade_version.get_git_sha.cache_clear()

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/git")

    def fake_run(*_args: Any, **_kwargs: Any) -> types.SimpleNamespace:
        return types.SimpleNamespace(stdout="deadbeef\n")

    monkeypatch.setattr(facade_version.subprocess, "run", fake_run)

    assert facade_version.get_git_sha() == "deadbeef"

    facade_version.get_git_sha.cache_clear()
