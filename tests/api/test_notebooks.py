from collections.abc import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from fastapi import Request
from theo.services.api.app.core.database import get_session
from theo.services.api.app.db.models import Document, Notebook
from theo.services.api.app.main import app
from theo.services.api.app.security import require_principal


@pytest.fixture()
def notebook_client(api_engine) -> Generator[tuple[TestClient, sessionmaker], None, None]:
    engine = api_engine
    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    def _override_session() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as client:
        yield client, factory

    app.dependency_overrides.pop(get_session, None)


def test_create_entry_rejects_invalid_osis(notebook_client) -> None:
    client, session_factory = notebook_client
    response = client.post("/notebooks/", json={"title": "Test Notebook"})
    assert response.status_code == 201
    notebook_id = response.json()["id"]

    invalid_entry = client.post(
        f"/notebooks/{notebook_id}/entries",
        json={"content": "Example note", "osis_ref": "NotAReference"},
    )

    assert invalid_entry.status_code == 400
    assert "Invalid OSIS" in invalid_entry.json()["detail"]


def test_create_entry_accepts_valid_references(notebook_client) -> None:
    client, session_factory = notebook_client
    with session_factory() as session:
        document = Document(id="doc-1", title="Sample")
        session.add(document)
        session.commit()

    response = client.post("/notebooks/", json={"title": "With Document"})
    assert response.status_code == 201
    notebook_id = response.json()["id"]

    entry_response = client.post(
        f"/notebooks/{notebook_id}/entries",
        json={
            "content": "Valid entry",
            "osis_ref": "John.1.1",
            "document_id": "doc-1",
        },
    )

    assert entry_response.status_code == 201
    payload = entry_response.json()
    assert payload["osis_ref"] == "John.1.1"
    assert payload["document_id"] == "doc-1"


def test_team_membership_enforced(notebook_client) -> None:
    client, _ = notebook_client

    def outsider(
        request: Request,
        authorization: str | None = None,
        api_key_header: str | None = None,
    ):
        principal = {"subject": "outsider", "claims": {}}
        request.state.principal = principal
        return principal

    app.dependency_overrides[require_principal] = outsider
    try:
        response = client.post(
            "/notebooks/",
            json={"title": "Team Notes", "team_id": "team-1"},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(require_principal, None)

    def team_member(
        request: Request,
        authorization: str | None = None,
        api_key_header: str | None = None,
    ):
        principal = {"subject": "member", "claims": {"teams": ["team-1"]}}
        request.state.principal = principal
        return principal

    app.dependency_overrides[require_principal] = team_member
    try:
        response = client.post(
            "/notebooks/",
            json={"title": "Team Notebook", "team_id": "team-1"},
        )
        assert response.status_code == 201
        assert response.json()["team_id"] == "team-1"
    finally:
        app.dependency_overrides.pop(require_principal, None)


def test_collaborator_can_update_entry(notebook_client) -> None:
    client, session_factory = notebook_client
    create_response = client.post(
        "/notebooks/",
        json={
            "title": "Shared",
            "collaborators": [{"subject": "ally", "role": "editor"}],
        },
    )
    assert create_response.status_code == 201
    notebook_id = create_response.json()["id"]

    entry_response = client.post(
        f"/notebooks/{notebook_id}/entries",
        json={"content": "Initial note", "osis_ref": "John.1.1"},
    )
    assert entry_response.status_code == 201
    entry_id = entry_response.json()["id"]

    def collaborator(
        request: Request,
        authorization: str | None = None,
        api_key_header: str | None = None,
    ):
        principal = {"subject": "ally", "claims": {}}
        request.state.principal = principal
        return principal

    app.dependency_overrides[require_principal] = collaborator
    try:
        update_response = client.patch(
            f"/notebooks/entries/{entry_id}",
            json={"content": "Updated by collaborator"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["content"] == "Updated by collaborator"
    finally:
        app.dependency_overrides.pop(require_principal, None)


@pytest.mark.no_auth_override
def test_list_notebooks_anonymous_only_public(
    notebook_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, session_factory = notebook_client

    from theo.services.api.app.core import settings as settings_module

    monkeypatch.setenv("THEO_AUTH_ALLOW_ANONYMOUS", "true")
    monkeypatch.setenv("THEO_API_KEYS", "[]")
    settings_module.get_settings.cache_clear()

    try:
        with session_factory() as session:
            public_notebook = Notebook(
                title="Public",
                created_by="owner-1",
                is_public=True,
            )
            private_notebook = Notebook(
                title="Private",
                created_by="owner-2",
                is_public=False,
            )
            session.add_all([public_notebook, private_notebook])
            session.commit()

            public_id = public_notebook.id
            private_id = private_notebook.id

        response = client.get("/notebooks/")
        assert response.status_code == 200

        payload = response.json()
        returned_ids = [notebook["id"] for notebook in payload["notebooks"]]
        assert returned_ids == [public_id]
        assert private_id not in returned_ids
    finally:
        settings_module.get_settings.cache_clear()
