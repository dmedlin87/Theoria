"""Regression tests for personalised watchlist routing."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Iterator

import pytest
from fastapi import Request as FastAPIRequest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades import database as database_module  # noqa: E402
from theo.application.facades.database import (  # noqa: E402
    Base,
    configure_engine,
    get_engine,
    get_session,
)
from theo.adapters.persistence.models import UserWatchlist  # noqa: E402
from theo.services.api.app.main import app  # noqa: E402
from theo.services.api.app.adapters.security import require_principal  # noqa: E402
from theo.services.api.app.routes.ai import watchlists as watchlists_module  # noqa: E402
from theo.services.api.app.routes.ai.watchlists import (  # noqa: E402
    WatchlistNotFoundError,
)


@pytest.fixture()
def watchlist_client(tmp_path: Path) -> Iterator[tuple[TestClient, Session]]:
    """Yield a TestClient connected to an isolated SQLite database."""

    configure_engine(f"sqlite:///{tmp_path / 'watchlists.db'}")
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    def _override_session():
        db = Session(engine)
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(require_principal, None)
        engine.dispose()
        database_module._engine = None  # type: ignore[attr-defined]
        database_module._SessionLocal = None  # type: ignore[attr-defined]


def _set_principal(subject: str) -> None:
    def _override(request: FastAPIRequest):
        principal = {"method": "override", "subject": subject}
        request.state.principal = principal
        return principal

    app.dependency_overrides[require_principal] = _override


def _fetch_watchlist(engine, watchlist_id: str) -> UserWatchlist | None:
    with Session(engine) as session:
        return session.get(UserWatchlist, watchlist_id)


class WatchlistsServiceStub:
    """Test double that records calls to the watchlist service API."""

    def __init__(self) -> None:
        self.raise_not_found_for: set[str] = set()
        self.delete_calls: list[tuple[str, str]] = []
        self.list_events_calls: list[tuple[str, str, datetime | None]] = []
        self.preview_calls: list[tuple[str, str]] = []
        self.run_calls: list[tuple[str, str]] = []
        now = datetime.now(timezone.utc)
        default_response = {
            "id": "run-id",
            "watchlist_id": "watchlist",
            "run_started": now,
            "run_completed": now,
            "window_start": now,
            "matches": [],
            "document_ids": [],
            "passage_ids": [],
            "delivery_status": None,
            "error": None,
        }
        self.list_events_return: list[dict[str, object]] = [default_response]
        self.preview_return: dict[str, object] = default_response
        self.run_return: dict[str, object] = default_response

    def _maybe_raise(self, method: str) -> None:
        if method in self.raise_not_found_for:
            raise WatchlistNotFoundError("watchlist not found")

    def delete(self, watchlist_id: str, user_id: str) -> None:
        self.delete_calls.append((watchlist_id, user_id))
        self._maybe_raise("delete")

    def list_events(
        self, watchlist_id: str, user_id: str, *, since: datetime | None
    ) -> list[dict[str, object]]:
        self.list_events_calls.append((watchlist_id, user_id, since))
        self._maybe_raise("list_events")
        return self.list_events_return

    def preview(self, watchlist_id: str, user_id: str) -> dict[str, object]:
        self.preview_calls.append((watchlist_id, user_id))
        self._maybe_raise("preview")
        return self.preview_return

    def run(self, watchlist_id: str, user_id: str) -> dict[str, object]:
        self.run_calls.append((watchlist_id, user_id))
        self._maybe_raise("run")
        return self.run_return


@pytest.fixture()
def watchlists_service_stub(monkeypatch: pytest.MonkeyPatch) -> WatchlistsServiceStub:
    stub = WatchlistsServiceStub()

    def _factory(_session: Session) -> WatchlistsServiceStub:
        return stub

    monkeypatch.setattr(watchlists_module, "_service", _factory)
    return stub


def test_create_watchlist_assigns_principal_subject(
    watchlist_client: tuple[TestClient, Session]
) -> None:
    client, engine = watchlist_client

    _set_principal("creator")
    response = client.post("/ai/digest/watchlists", json={"name": "Creator Watchlist"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["user_id"] == "creator"

    stored = _fetch_watchlist(engine, payload["id"])
    assert stored is not None
    assert stored.user_id == "creator"


def test_list_watchlists_filters_by_principal_subject(
    watchlist_client: tuple[TestClient, Session]
) -> None:
    client, _ = watchlist_client

    _set_principal("alpha")
    first = client.post("/ai/digest/watchlists", json={"name": "Alpha Watchlist"})
    assert first.status_code == 201

    _set_principal("beta")
    second = client.post("/ai/digest/watchlists", json={"name": "Beta Watchlist"})
    assert second.status_code == 201

    _set_principal("alpha")
    alpha_response = client.get("/ai/digest/watchlists")
    assert alpha_response.status_code == 200
    alpha_payload = alpha_response.json()
    assert [item["user_id"] for item in alpha_payload] == ["alpha"]
    assert alpha_payload[0]["name"] == "Alpha Watchlist"

    _set_principal("beta")
    beta_response = client.get("/ai/digest/watchlists")
    assert beta_response.status_code == 200
    beta_payload = beta_response.json()
    assert [item["user_id"] for item in beta_payload] == ["beta"]
    assert beta_payload[0]["name"] == "Beta Watchlist"


def test_other_user_watchlist_returns_not_found(
    watchlist_client: tuple[TestClient, Session]
) -> None:
    client, engine = watchlist_client

    _set_principal("owner")
    created = client.post("/ai/digest/watchlists", json={"name": "Owner Watchlist"})
    assert created.status_code == 201
    watchlist_id = created.json()["id"]

    _set_principal("intruder")
    response = client.patch(
        f"/ai/digest/watchlists/{watchlist_id}", json={"name": "Intruder Watchlist"}
    )
    assert response.status_code in {403, 404}

    stored = _fetch_watchlist(engine, watchlist_id)
    assert stored is not None
    assert stored.name == "Owner Watchlist"

    _set_principal("owner")
    update_response = client.patch(
        f"/ai/digest/watchlists/{watchlist_id}", json={"name": "Updated Watchlist"}
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Updated Watchlist"


def test_delete_watchlist_uses_principal_subject(
    watchlist_client: tuple[TestClient, Session],
    watchlists_service_stub: WatchlistsServiceStub,
) -> None:
    client, _ = watchlist_client

    _set_principal("deleter")
    response = client.delete("/ai/digest/watchlists/watch-123")

    assert response.status_code == 204
    assert watchlists_service_stub.delete_calls == [("watch-123", "deleter")]


def test_delete_watchlist_returns_not_found_error(
    watchlist_client: tuple[TestClient, Session],
    watchlists_service_stub: WatchlistsServiceStub,
) -> None:
    client, _ = watchlist_client
    watchlists_service_stub.raise_not_found_for.add("delete")

    _set_principal("deleter")
    response = client.delete("/ai/digest/watchlists/missing")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "AI_WATCHLIST_NOT_FOUND"
    assert payload["detail"] == "Watchlist not found"
    assert watchlists_service_stub.delete_calls == [("missing", "deleter")]


def test_watchlist_events_forward_since_parameter(
    watchlist_client: tuple[TestClient, Session],
    watchlists_service_stub: WatchlistsServiceStub,
) -> None:
    client, _ = watchlist_client
    since = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    watchlists_service_stub.list_events_return = [
        {
            "id": "event-1",
            "watchlist_id": "watch-abc",
            "run_started": since,
            "run_completed": since,
            "window_start": since,
            "matches": [],
            "document_ids": [],
            "passage_ids": [],
            "delivery_status": "delivered",
            "error": None,
        }
    ]

    _set_principal("reader")
    response = client.get(
        "/ai/digest/watchlists/watch-abc/events",
        params={"since": since.isoformat()},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "event-1",
            "watchlist_id": "watch-abc",
            "run_started": since.isoformat(),
            "run_completed": since.isoformat(),
            "window_start": since.isoformat(),
            "matches": [],
            "document_ids": [],
            "passage_ids": [],
            "delivery_status": "delivered",
            "error": None,
        }
    ]
    assert watchlists_service_stub.list_events_calls == [
        ("watch-abc", "reader", since)
    ]


def test_preview_watchlist_returns_stub_payload(
    watchlist_client: tuple[TestClient, Session],
    watchlists_service_stub: WatchlistsServiceStub,
) -> None:
    client, _ = watchlist_client
    now = datetime(2024, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
    watchlists_service_stub.preview_return = {
        "id": "preview-1",
        "watchlist_id": "watch-preview",
        "run_started": now,
        "run_completed": now,
        "window_start": now,
        "matches": [],
        "document_ids": [],
        "passage_ids": [],
        "delivery_status": None,
        "error": None,
    }

    _set_principal("runner")
    response = client.get("/ai/digest/watchlists/watch-preview/preview")

    assert response.status_code == 200
    assert response.json() == {
        "id": "preview-1",
        "watchlist_id": "watch-preview",
        "run_started": now.isoformat(),
        "run_completed": now.isoformat(),
        "window_start": now.isoformat(),
        "matches": [],
        "document_ids": [],
        "passage_ids": [],
        "delivery_status": None,
        "error": None,
    }
    assert watchlists_service_stub.preview_calls == [("watch-preview", "runner")]


def test_run_watchlist_returns_stub_payload(
    watchlist_client: tuple[TestClient, Session],
    watchlists_service_stub: WatchlistsServiceStub,
) -> None:
    client, _ = watchlist_client
    now = datetime(2024, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
    watchlists_service_stub.run_return = {
        "id": "run-1",
        "watchlist_id": "watch-run",
        "run_started": now,
        "run_completed": now,
        "window_start": now,
        "matches": [],
        "document_ids": [],
        "passage_ids": [],
        "delivery_status": "queued",
        "error": None,
    }

    _set_principal("runner")
    response = client.post("/ai/digest/watchlists/watch-run/run")

    assert response.status_code == 200
    assert response.json() == {
        "id": "run-1",
        "watchlist_id": "watch-run",
        "run_started": now.isoformat(),
        "run_completed": now.isoformat(),
        "window_start": now.isoformat(),
        "matches": [],
        "document_ids": [],
        "passage_ids": [],
        "delivery_status": "queued",
        "error": None,
    }
    assert watchlists_service_stub.run_calls == [("watch-run", "runner")]


@pytest.mark.parametrize(
    "method,path",
    [
        ("delete", "/ai/digest/watchlists/watch-123"),
        ("get", "/ai/digest/watchlists/watch-123/events"),
        ("get", "/ai/digest/watchlists/watch-123/preview"),
        ("post", "/ai/digest/watchlists/watch-123/run"),
    ],
)
def test_watchlist_routes_require_subject(
    watchlist_client: tuple[TestClient, Session],
    watchlists_service_stub: WatchlistsServiceStub,
    method: str,
    path: str,
) -> None:
    client, _ = watchlist_client

    _set_principal("")
    response = client.request(method, path)

    assert response.status_code == 403
    payload = response.json()
    assert payload["error"]["code"] == "AI_WATCHLIST_FORBIDDEN"
    assert payload["detail"] == "Forbidden"
    assert watchlists_service_stub.delete_calls == []
    assert watchlists_service_stub.list_events_calls == []
    assert watchlists_service_stub.preview_calls == []
    assert watchlists_service_stub.run_calls == []
