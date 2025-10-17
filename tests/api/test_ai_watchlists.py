"""Regression tests for personalised watchlist routing."""
from __future__ import annotations

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
from theo.services.api.app.security import require_principal  # noqa: E402


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
