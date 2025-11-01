"""Behavioural tests for critical API routes."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

API_KEY = "test-route-key"

os.environ.setdefault("THEO_DISABLE_AI_SETTINGS", "1")
os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("SETTINGS_SECRET_KEY", "tests-secret-key")
os.environ.setdefault("THEORIA_ENVIRONMENT", "test")
os.environ.setdefault("THEO_AUTH_ALLOW_ANONYMOUS", "0")
os.environ.setdefault("THEO_API_KEYS", API_KEY)

from theo.adapters.persistence import Base  # noqa: E402
from theo.application.facades.database import get_session  # noqa: E402
from theo.application.facades.settings import get_settings  # noqa: E402
from theo.infrastructure.api.app.adapters.security import require_principal  # noqa: E402
from theo.infrastructure.api.app.main import app  # noqa: E402
from theo.infrastructure.api.app.tracing import TRACE_ID_HEADER_NAME  # noqa: E402


@pytest.fixture(autouse=True)
def _refresh_settings_cache() -> Iterator[None]:
    """Ensure each test observes fresh settings values."""

    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


@contextmanager
def _override_session(engine: Engine, *, create_schema: bool) -> Iterator[None]:
    """Override the application DB session with one backed by *engine*."""

    session_factory = sessionmaker(bind=engine, future=True)

    if create_schema:
        Base.metadata.create_all(engine)

    def _session_override() -> Iterator[Session]:
        with session_factory() as db_session:
            yield db_session

    app.dependency_overrides[get_session] = _session_override
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_session, None)
        if create_schema:
            Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def sqlite_client() -> Iterator[TestClient]:
    """Provide a test client backed by an isolated SQLite database."""

    engine = create_engine("sqlite:///:memory:", future=True)
    with _override_session(engine, create_schema=True):
        with TestClient(app) as client:
            yield client


def test_watchlist_requires_authentication(sqlite_client: TestClient) -> None:
    """POST /ai/digest/watchlists should enforce authentication."""

    payload = {
        "name": "Weekly Hope",
        "filters": {"osis": ["John 3:16"]},
        "cadence": "weekly",
    }

    response = sqlite_client.post("/ai/digest/watchlists", json=payload)

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json()["detail"] == "Missing credentials"


def test_watchlist_forbidden_without_subject(sqlite_client: TestClient) -> None:
    """A resolved principal without a subject should raise a domain error."""

    async def _principal_override(request):  # type: ignore[override]
        principal = {
            "method": "override",
            "subject": None,
            "scopes": [],
            "claims": {},
            "token": "",
        }
        request.state.principal = principal
        return principal

    app.dependency_overrides[require_principal] = _principal_override
    try:
        response = sqlite_client.get(
            "/ai/digest/watchlists",
            headers={"X-API-Key": API_KEY},
        )
    finally:
        app.dependency_overrides.pop(require_principal, None)

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "AI_WATCHLIST_FORBIDDEN"
    assert body["detail"] == "Forbidden"


def test_search_invalid_experiments_returns_bad_request(sqlite_client: TestClient) -> None:
    """Supplying too many experiment tokens should yield a validation error."""

    params = [("experiment", f"flag-{index}") for index in range(25)]

    response = sqlite_client.get(
        "/search/",
        params=params,
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 400
    assert "limit is" in response.json()["detail"]


def test_search_unexpected_error_returns_internal_error(
    sqlite_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unhandled exceptions should be transformed into a 500 response."""

    class _FailingRetrievalService:
        def search(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "theo.infrastructure.api.app.routes.search.get_retrieval_service",
        lambda *_args, **_kwargs: _FailingRetrievalService(),
    )

    response = sqlite_client.get(
        "/search/",
        params={"q": "hope"},
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal Server Error"
    assert "trace_id" in body
    assert TRACE_ID_HEADER_NAME in response.headers


@pytest.mark.pgvector
def test_chat_session_not_found_returns_domain_error(
    pgvector_migrated_database_url: str,
) -> None:
    """GET /ai/chat/{session_id} should surface a domain error for missing sessions."""

    engine = create_engine(pgvector_migrated_database_url, future=True)
    with _override_session(engine, create_schema=False):
        with TestClient(app) as client:
            response = client.get(
                "/ai/chat/non-existent-session",
                headers={"X-API-Key": API_KEY},
            )

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "AI_CHAT_SESSION_NOT_FOUND"
    assert body["detail"] == "chat session not found"
