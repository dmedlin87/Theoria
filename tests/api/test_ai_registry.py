from __future__ import annotations

from pathlib import Path
from typing import Iterator
import sys

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.ai.clients import (  # noqa: E402
    AIClientSettings,
    AnthropicClient,
    AnthropicConfig,
    AzureOpenAIClient,
    AzureOpenAIConfig,
    LocalVLLMClient,
    LocalVLLMConfig,
    OpenAIClient,
    OpenAIConfig,
    VertexAIClient,
    VertexAIConfig,
    build_client,
)
from theo.services.api.app.ai.registry import (  # noqa: E402
    LLMModel,
    get_llm_registry,
    save_llm_registry,
)
from sqlalchemy.engine import Engine

from theo.application.facades import database as database_module  # noqa: E402
from theo.application.facades.database import (  # noqa: E402
    Base,
    configure_engine,
    get_engine,
    get_session,
)
from theo.application.facades.secret_migration import (  # noqa: E402
    migrate_secret_settings,
)
from theo.application.facades.settings import (  # noqa: E402
    get_settings,
    get_settings_cipher,
)
from theo.application.facades.settings_store import (  # noqa: E402
    load_setting,
    save_setting,
)
from theo.adapters.persistence.models import AppSetting  # noqa: E402
from theo.services.api.app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch):
    monkeypatch.setenv("SETTINGS_SECRET_KEY", "test-secret-key")
    get_settings.cache_clear()
    get_settings_cipher.cache_clear()
    yield
    get_settings.cache_clear()
    get_settings_cipher.cache_clear()


def _prepare_engine(tmp_path: Path) -> Engine:
    configure_engine(f"sqlite:///{tmp_path / 'llm.db'}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return engine


class StubHTTPXClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def request(self, method: str, url: str, **kwargs):
        if not self._responses:
            raise AssertionError("No more responses configured")
        factory = self._responses.pop(0)
        self.calls.append((method, url, kwargs))
        if isinstance(factory, Exception):
            raise factory
        return factory(method, url, kwargs)


def json_response(
    status_code: int, payload: dict, headers: dict | None = None
):
    def _factory(method: str, url: str, kwargs: dict):
        request = httpx.Request(method, f"https://example.test{url}")
        return httpx.Response(status_code, headers=headers, json=payload, request=request)

    return _factory


@pytest.fixture()
def api_client(tmp_path: Path) -> Iterator[TestClient]:
    """Provide a TestClient wired to a temporary SQLite database."""

    engine = _prepare_engine(tmp_path)

    def _override_session():
        db = Session(engine)
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_settings_store_encrypts_and_decrypts(tmp_path: Path) -> None:
    engine = _prepare_engine(tmp_path)
    try:
        with Session(engine) as session:
            save_setting(session, "secrets", {"token": "value"})
            record = session.get(AppSetting, "app:secrets")
            assert record is not None
            assert isinstance(record.value, dict)
            assert "__encrypted__" in record.value
            assert load_setting(session, "secrets") == {"token": "value"}
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_registry_encrypts_api_keys_and_migrates_plaintext(tmp_path: Path) -> None:
    engine = _prepare_engine(tmp_path)
    payload = {
        "default_model": "anthropic",
        "models": [
            {
                "name": "anthropic",
                "provider": "anthropic",
                "model": "claude-3",
                "config": {"api_key": "plain-key"},
            }
        ],
    }
    try:
        with Session(engine) as session:
            session.add(AppSetting(key="app:llm", value=payload))
            session.commit()

            registry = get_llm_registry(session)
            model = registry.get("anthropic")
            assert model.config["api_key"] == "plain-key"

            record = session.get(AppSetting, "app:llm")
            assert record is not None
            assert isinstance(record.value, dict)
            assert "__encrypted__" in record.value

            serialized = registry.serialize()
            stored_config = serialized["models"][0]["config"]["api_key"]
            assert isinstance(stored_config, dict)
            assert "__encrypted__" in stored_config
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_migrate_plaintext_settings_reencrypts(tmp_path: Path) -> None:
    engine = _prepare_engine(tmp_path)
    llm_payload = {
        "default_model": "anthropic",
        "models": [
            {
                "name": "anthropic",
                "provider": "anthropic",
                "model": "claude-3",
                "config": {"api_key": "plain-key"},
            }
        ],
    }
    provider_payload = {
        "openai": {
            "api_key": "provider-secret",
            "base_url": "https://api.openai.example",
        }
    }

    try:
        with Session(engine) as session:
            session.add(AppSetting(key="app:llm", value=llm_payload))
            session.add(AppSetting(key="app:ai_providers", value=provider_payload))
            session.commit()

            migrated = migrate_secret_settings(session)
            assert set(migrated) == {"llm", "ai_providers"}

            llm_record = session.get(AppSetting, "app:llm")
            assert llm_record is not None
            assert isinstance(llm_record.value, dict)
            assert "__encrypted__" in llm_record.value

            provider_record = session.get(AppSetting, "app:ai_providers")
            assert provider_record is not None
            assert isinstance(provider_record.value, dict)
            assert "__encrypted__" in provider_record.value

            registry = get_llm_registry(session)
            model = registry.get("anthropic")
            assert model.config["api_key"] == "plain-key"

            providers = load_setting(session, "ai_providers")
            assert providers is not None
            assert providers["openai"]["api_key"] == "provider-secret"

            registry.add_model(
                LLMModel(
                    name="azure",
                    provider="azure",
                    model="gpt-4o",
                    config={
                        "api_key": "new-secret",
                        "endpoint": "https://example.azure.com",
                        "deployment": "prod",
                    },
                )
            )
            save_llm_registry(session, registry)

            save_setting(
                session,
                "ai_providers",
                {
                    "openai": {
                        "api_key": "rotated",
                        "base_url": "https://api.openai.example",
                    }
                },
            )

            session.expire_all()

            llm_record = session.get(AppSetting, "app:llm")
            assert llm_record is not None
            assert isinstance(llm_record.value, dict)
            assert "__encrypted__" in llm_record.value

            provider_record = session.get(AppSetting, "app:ai_providers")
            assert provider_record is not None
            assert isinstance(provider_record.value, dict)
            assert "__encrypted__" in provider_record.value

            providers = load_setting(session, "ai_providers")
            assert providers is not None
            assert providers["openai"]["api_key"] == "rotated"
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "provider, config, expected",
    [
        ("openai", {"api_key": "key"}, OpenAIClient),
        (
            "azure",
            {
                "api_key": "key",
                "endpoint": "https://example.openai.azure.com",
                "deployment": "gpt",
            },
            AzureOpenAIClient,
        ),
        ("anthropic", {"api_key": "key"}, AnthropicClient),
        (
            "vertex",
            {
                "project_id": "proj",
                "location": "us-central1",
                "model": "text-model",
                "access_token": "token",
            },
            VertexAIClient,
        ),
        (
            "vllm",
            {
                "base_url": "http://localhost:8000",
            },
            LocalVLLMClient,
        ),
    ],
)
def test_build_client_dispatch(provider, config, expected) -> None:
    client = build_client(provider, config)
    assert isinstance(client, expected)


def test_registry_persists_model_metadata(tmp_path: Path) -> None:
    engine = _prepare_engine(tmp_path)
    try:
        with Session(engine) as session:
            registry = get_llm_registry(session)
            model = LLMModel(
                name="primary",
                provider="echo",
                model="echo",
                config={"suffix": "[ok]"},
                pricing={"per_call": 0.5},
                latency={"p95": 1200},
                routing={"spend_ceiling": 5.0, "weight": 2.5},
            )
            registry.add_model(model, make_default=True)
            save_llm_registry(session, registry)
            session.expire_all()

            reloaded = get_llm_registry(session)
            loaded = reloaded.get("primary")
            assert loaded.pricing["per_call"] == 0.5
            assert loaded.latency["p95"] == 1200
            assert loaded.routing["spend_ceiling"] == 5.0
    finally:
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def test_llm_routes_persist_metadata(api_client: TestClient) -> None:
    payload = {
        "name": "primary",
        "provider": "echo",
        "model": "echo",
        "config": {"suffix": "[ok]"},
        "pricing": {"per_call": 0.25},
        "latency": {"p95": 900},
        "routing": {"weight": 1.5},
        "make_default": True,
    }

    create_response = api_client.post("/ai/llm", json=payload)
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["default_model"] == "primary"
    stored_model = created["models"][0]
    assert stored_model["pricing"]["per_call"] == 0.25
    assert stored_model["latency"]["p95"] == 900
    assert stored_model["routing"]["weight"] == 1.5

    list_response = api_client.get("/ai/llm")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["default_model"] == "primary"
    listed = payload["models"][0]
    assert listed["pricing"]["per_call"] == 0.25
    assert listed["latency"]["p95"] == 900
    assert listed["routing"]["weight"] == 1.5


def test_llm_routes_openapi_schema(api_client: TestClient) -> None:
    schema_response = api_client.get("/openapi.json")
    assert schema_response.status_code == 200
    schema = schema_response.json()

    llm_paths = schema["paths"]["/ai/llm"]
    assert set(llm_paths.keys()) == {"get", "post"}

    llm_default = schema["paths"].get("/ai/llm/default")
    assert llm_default is not None
    assert set(llm_default.keys()) == {"patch"}

    llm_model = schema["paths"].get("/ai/llm/{name}")
    assert llm_model is not None
    assert set(llm_model.keys()) == {"patch", "delete"}


def test_retry_backoff_respects_retry_after() -> None:
    fake_time = [0.0]
    sleep_calls: list[float] = []

    def fake_clock() -> float:
        return fake_time[0]

    def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)
        fake_time[0] += duration

    settings = AIClientSettings(
        max_attempts=3,
        backoff_initial=1.0,
        backoff_multiplier=2.0,
        backoff_max=10.0,
        total_timeout=20.0,
        request_timeout=5.0,
        read_timeout=5.0,
        clock=fake_clock,
        sleep=fake_sleep,
    )

    client = AnthropicClient(AnthropicConfig(api_key="test"), settings=settings)
    responses = [
        json_response(429, {"error": "rate"}, headers={"Retry-After": "2"}),
        json_response(503, {"error": "busy"}, headers={"retry-after-ms": "1500"}),
        json_response(200, {"content": [{"text": "final"}]}),
    ]
    stub = StubHTTPXClient(responses)
    client._client = stub  # type: ignore[attr-defined]

    result = client.generate(prompt="hello", model="claude-3")

    assert result == "final"
    assert len(stub.calls) == 3
    assert sleep_calls == pytest.approx([2.0, 1.5])


@pytest.mark.parametrize(
    "factory, payload, header_name, expected",
    [
        (
            lambda settings: OpenAIClient(
                OpenAIConfig(api_key="key", base_url="https://openai.example"),
                settings=settings,
            ),
            {"choices": [{"message": {"content": "openai"}}]},
            "Idempotency-Key",
            "openai",
        ),
        (
            lambda settings: AzureOpenAIClient(
                AzureOpenAIConfig(
                    api_key="key",
                    endpoint="https://azure.example",
                    deployment="deploy",
                ),
                settings=settings,
            ),
            {"choices": [{"message": {"content": "azure"}}]},
            "x-ms-client-request-id",
            "azure",
        ),
        (
            lambda settings: AnthropicClient(
                AnthropicConfig(api_key="key"),
                settings=settings,
            ),
            {"content": [{"text": "anthropic"}]},
            "anthropic-idempotency-key",
            "anthropic",
        ),
        (
            lambda settings: VertexAIClient(
                VertexAIConfig(
                    project_id="proj",
                    location="us-central1",
                    model="text-model",
                    access_token="token",
                ),
                settings=settings,
            ),
            {"predictions": [{"content": "vertex"}]},
            "x-request-id",
            "vertex",
        ),
        (
            lambda settings: LocalVLLMClient(
                LocalVLLMConfig(base_url="https://local.example"),
                settings=settings,
            ),
            {"choices": [{"message": {"content": "local"}}]},
            "Idempotency-Key",
            "local",
        ),
    ],
)
def test_clients_inject_idempotency_keys_and_cache(
    factory, payload, header_name, expected
) -> None:
    fake_time = [0.0]

    settings = AIClientSettings(
        max_attempts=1,
        total_timeout=30.0,
        request_timeout=5.0,
        read_timeout=5.0,
        clock=lambda: fake_time[0],
        sleep=lambda _: None,
    )

    client = factory(settings)
    stub = StubHTTPXClient([json_response(200, payload)])
    client._client = stub  # type: ignore[attr-defined]

    result_one = client.generate(prompt="hello", model="model", cache_key="cache-key")
    result_two = client.generate(prompt="hello", model="model", cache_key="cache-key")

    assert result_one == expected
    assert result_two == expected
    assert len(stub.calls) == 1
    headers = stub.calls[0][2]["headers"]
    assert headers[header_name] == "cache-key"
