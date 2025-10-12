import os

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDenialResponse

from theo.application.facades import settings as settings_module
from theo.application.facades.database import get_session
from theo.services.api.app.routes import realtime
from theo.services.api.app.routes.realtime import NotebookEventBroker


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class DummyWebSocket:
    def __init__(self, name: str) -> None:
        self.name = name
        self.accepted = 0

    async def accept(self) -> None:
        self.accepted += 1

    async def send_json(self, message):
        # The broker may attempt to send messages during broadcast tests.
        # These tests focus on connection bookkeeping, so sending is a no-op.
        self.last_message = message


async def test_disconnect_removes_empty_connection_sets() -> None:
    broker = NotebookEventBroker()
    websocket = DummyWebSocket("ws-1")

    await broker.connect("notebook-1", websocket)
    assert "notebook-1" in broker._connections

    await broker.disconnect("notebook-1", websocket)

    assert "notebook-1" not in broker._connections


async def test_disconnect_retains_non_empty_sets_until_last_connection_removed() -> None:
    broker = NotebookEventBroker()
    first = DummyWebSocket("ws-1")
    second = DummyWebSocket("ws-2")

    await broker.connect("notebook-2", first)
    await broker.connect("notebook-2", second)

    await broker.disconnect("notebook-2", first)

    assert "notebook-2" in broker._connections
    assert broker._connections["notebook-2"] == {second}

    await broker.disconnect("notebook-2", second)

    assert "notebook-2" not in broker._connections


@pytest.fixture()
def realtime_client() -> TestClient:
    app = FastAPI()
    app.include_router(realtime.router, prefix="/realtime")

    os.environ.setdefault("THEO_API_KEYS", '["pytest-default-key"]')
    settings_module.get_settings.cache_clear()
    settings = settings_module.get_settings()
    assert settings.api_keys, "API keys must be configured for authentication tests"

    class _DummySession:
        def get(self, *_args, **_kwargs):
            return None

    def _override_session():
        yield _DummySession()

    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as client:
        yield client
    settings_module.get_settings.cache_clear()


@pytest.mark.no_auth_override
def test_realtime_poll_requires_authentication(realtime_client: TestClient) -> None:
    response = realtime_client.get("/realtime/notebooks/example/poll")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.no_auth_override
def test_realtime_websocket_requires_authentication(realtime_client: TestClient) -> None:
    with pytest.raises(WebSocketDenialResponse) as exc:
        with realtime_client.websocket_connect("/realtime/notebooks/example"):
            pytest.fail("Unauthenticated websocket should not be accepted")

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
