from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from contextlib import contextmanager
import sys
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades.database import get_session
from theo.application.facades.settings import get_settings
from theo.services.api.app.main import app
from theo.services.api.app.routes import ai as ai_module
from theo.services.api.app.routes import documents as documents_module
from theo.services.api.app.routes import ingest as ingest_module


pytestmark = pytest.mark.no_auth_override


class _DummyScalarResult:
    def all(self) -> list[Any]:
        return []


class _DummyResult:
    def scalars(self) -> _DummyScalarResult:
        return _DummyScalarResult()


class _DummySession:
    def execute(self, _stmt):
        return _DummyResult()

    def get(self, _model, _pk):
        return None


@pytest.fixture(autouse=True)
def _refresh_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def secure_env(monkeypatch) -> dict[str, str]:
    monkeypatch.setenv("THEO_API_KEYS", '["valid-key"]')
    monkeypatch.setenv("THEO_AUTH_JWT_SECRET", "shared-secret")
    monkeypatch.delenv("THEO_AUTH_JWT_ALGORITHMS", raising=False)
    monkeypatch.delenv("THEO_AUTH_JWT_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("THEO_AUTH_JWT_PUBLIC_KEY_PATH", raising=False)
    monkeypatch.delenv("THEO_AUTH_ALLOW_ANONYMOUS", raising=False)
    return {"api_key": "valid-key", "jwt_secret": "shared-secret"}


@pytest.fixture
def api_client(monkeypatch, secure_env):
    with _client_context(monkeypatch) as client:
        yield client


@pytest.fixture
def anonymous_client(monkeypatch):
    monkeypatch.delenv("THEO_API_KEYS", raising=False)
    monkeypatch.delenv("THEO_AUTH_JWT_SECRET", raising=False)
    monkeypatch.delenv("THEO_AUTH_JWT_ALGORITHMS", raising=False)
    monkeypatch.delenv("THEO_AUTH_JWT_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("THEO_AUTH_JWT_PUBLIC_KEY_PATH", raising=False)
    monkeypatch.setenv("THEO_AUTH_ALLOW_ANONYMOUS", "1")
    with _client_context(monkeypatch) as client:
        yield client


@pytest.fixture
def rsa_keys() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


@pytest.fixture
def rsa_client(monkeypatch, rsa_keys):
    private_pem, public_pem = rsa_keys
    monkeypatch.setenv("THEO_API_KEYS", '["valid-key"]')
    monkeypatch.delenv("THEO_AUTH_JWT_SECRET", raising=False)
    monkeypatch.setenv("THEO_AUTH_JWT_ALGORITHMS", '["RS256"]')
    monkeypatch.setenv("THEO_AUTH_JWT_PUBLIC_KEY", public_pem)
    monkeypatch.delenv("THEO_AUTH_JWT_PUBLIC_KEY_PATH", raising=False)
    monkeypatch.delenv("THEO_AUTH_ALLOW_ANONYMOUS", raising=False)
    with _client_context(monkeypatch) as client:
        yield client, private_pem


@contextmanager
def _client_context(monkeypatch):
    def _override_session():
        yield _DummySession()

    app.dependency_overrides[get_session] = _override_session
    try:
        monkeypatch.setattr(
            "theo.services.api.app.main.run_sql_migrations",
            lambda *args, **kwargs: [],
        )
        monkeypatch.setattr(
            "theo.services.api.app.main.seed_reference_data",
            lambda *args, **kwargs: None,
        )

        def _fake_pipeline(session, url, **kwargs):  # noqa: ANN001 - signature controlled by patch
            class _Doc:
                id = "doc-1"

            return _Doc()

        monkeypatch.setattr(ingest_module, "run_pipeline_for_url", _fake_pipeline)

        class _Registry:
            def to_response(self) -> dict[str, Any]:
                return {"models": [], "default_model": None}

        monkeypatch.setattr(ai_module, "get_llm_registry", lambda session: _Registry())

        def _fake_digest(session, since):
            return ai_module.TopicDigest(
                generated_at=datetime.now(UTC),
                window_start=datetime.now(UTC) - timedelta(hours=1),
                topics=[],
            )

        monkeypatch.setattr(ai_module, "generate_topic_digest", _fake_digest)
        monkeypatch.setattr(ai_module, "upsert_digest_document", lambda *args, **kwargs: None)
        monkeypatch.setattr(ai_module, "store_topic_digest", lambda *args, **kwargs: None)

        def _fake_list_documents(session, limit: int, offset: int):
            return documents_module.DocumentListResponse(
                items=[], total=0, limit=limit, offset=offset
            )

        monkeypatch.setattr(documents_module, "list_documents", _fake_list_documents)

        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("post", "/ingest/url", {"json": {"url": "https://example.com"}}),
        ("get", "/ai/llm", {}),
        ("post", "/ai/digest", {}),
        ("get", "/documents", {}),
        ("get", "/jobs", {}),
    ],
)
def test_missing_credentials_return_unauthorized(api_client, method: str, path: str, kwargs: dict[str, Any]):
    response = getattr(api_client, method)(path, **kwargs)
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("post", "/ingest/url", {"json": {"url": "https://example.com"}}),
        ("get", "/ai/llm", {}),
        ("post", "/ai/digest", {}),
        ("get", "/documents", {}),
        ("get", "/jobs", {}),
    ],
)
def test_invalid_credentials_return_forbidden(api_client, method: str, path: str, kwargs: dict[str, Any]):
    response = getattr(api_client, method)(
        path, headers={"Authorization": "Bearer invalid"}, **kwargs
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("post", "/ingest/url", {"json": {"url": "https://example.com"}}),
        ("get", "/ai/llm", {}),
        ("post", "/ai/digest", {}),
        ("get", "/documents", {}),
        ("get", "/jobs", {}),
    ],
)
def test_api_key_allows_access(api_client, method: str, path: str, kwargs: dict[str, Any]):
    response = getattr(api_client, method)(
        path, headers={"X-API-Key": "valid-key"}, **kwargs
    )
    assert response.status_code == 200


def test_hs256_jwt_allows_access(api_client):
    token = jwt.encode({"sub": "test-user"}, "shared-secret", algorithm="HS256")
    response = api_client.get("/documents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_anonymous_access_allowed_when_auth_unconfigured(anonymous_client):
    response = anonymous_client.get("/documents")
    assert response.status_code == 200


def test_rs256_jwt_allows_access(rsa_client):
    client, private_key = rsa_client
    token = jwt.encode({"sub": "rs-user"}, private_key, algorithm="RS256")
    response = client.get("/documents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
