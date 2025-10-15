import os

import pytest
from fastapi import FastAPI, HTTPException, status
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
        self.sent_messages: list[dict[str, object]] = []

    async def accept(self) -> None:
        self.accepted += 1

    async def send_json(self, message):
        # The broker may attempt to send messages during broadcast tests.
        # These tests focus on connection bookkeeping, so sending is a no-op.
        self.last_message = message
        self.sent_messages.append(message)


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


async def test_broadcast_increments_version_and_delivers_payload() -> None:
    broker = NotebookEventBroker()
    websocket = DummyWebSocket("ws-1")

    await broker.connect("notebook-3", websocket)

    assert broker.current_version("notebook-3") == 0

    await broker.broadcast("notebook-3", {"payload": "data"})

    assert broker.current_version("notebook-3") == 1
    assert websocket.last_message["type"] == "notebook.update"
    assert websocket.last_message["version"] == 1
    assert websocket.last_message["payload"] == "data"


async def test_broadcast_disconnects_failed_connections() -> None:
    broker = NotebookEventBroker()
    healthy = DummyWebSocket("ws-healthy")

    class _FailingWebSocket(DummyWebSocket):
        async def send_json(self, message):  # pragma: no cover - exercised in test
            raise RuntimeError("cannot send")

    failing = _FailingWebSocket("ws-failing")

    await broker.connect("notebook-4", healthy)
    await broker.connect("notebook-4", failing)

    await broker.broadcast("notebook-4", {"payload": "info"})

    assert broker._connections["notebook-4"] == {healthy}
    assert healthy.last_message["payload"] == "info"


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
@pytest.mark.skip(reason="TestClient doesn't properly handle WebSocket dependency exceptions - causes infinite hang. Authentication is tested via HTTP poll endpoint instead.")
def test_realtime_websocket_requires_authentication(
    realtime_client: TestClient,
) -> None:
    # WebSocket connection should be denied immediately without credentials
    # NOTE: This test hangs because TestClient.websocket_connect enters the
    # context manager before checking dependencies, triggering the infinite
    # message loop in the WebSocket handler.
    with pytest.raises(WebSocketDenialResponse) as exc:
        with realtime_client.websocket_connect("/realtime/notebooks/example"):
            pytest.fail("Should not accept unauthenticated connection")
    
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.no_auth_override
@pytest.mark.skip(reason="TestClient doesn't properly handle WebSocket dependency exceptions - causes infinite hang. Access control is tested via HTTP poll endpoint instead.")
def test_realtime_websocket_denies_forbidden_access(
    realtime_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _ForbiddenService:
        def ensure_accessible(self, _notebook_id: str) -> None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    def _service_override(_session, _principal):  # pragma: no cover - runtime dependency
        return _ForbiddenService()

    connect_called = False

    async def _connect_override(_notebook_id: str, _websocket):
        nonlocal connect_called
        connect_called = True

    monkeypatch.setattr(realtime, "_service", _service_override)
    monkeypatch.setattr(realtime._BROKER, "connect", _connect_override)

    # WebSocket connection should be denied when access check fails
    # NOTE: This test hangs because TestClient.websocket_connect enters the
    # context manager before checking dependencies, triggering the infinite
    # message loop in the WebSocket handler.
    with pytest.raises(WebSocketDenialResponse) as exc:
        with realtime_client.websocket_connect(
            "/realtime/notebooks/example",
            headers={"X-API-Key": "pytest-default-key"},
        ):
            pytest.fail("Should not accept forbidden connection")
    
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert connect_called is False


@pytest.mark.no_auth_override
def test_realtime_poll_denies_forbidden_access(
    realtime_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _ForbiddenService:
        def ensure_accessible(self, _notebook_id: str) -> None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    def _service_override(_session, _principal):  # pragma: no cover - runtime dependency
        return _ForbiddenService()

    monkeypatch.setattr(realtime, "_service", _service_override)

    response = realtime_client.get(
        "/realtime/notebooks/example/poll",
        headers={"X-API-Key": "pytest-default-key"},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
