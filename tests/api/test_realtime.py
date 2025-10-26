import os
from inspect import isawaitable

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from starlette.websockets import WebSocket

from theo.application.facades import settings as settings_module
from theo.application.facades.database import get_session
from theo.services.api.app.adapters.security import configure_principal_resolver
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
def realtime_app() -> FastAPI:
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
    configure_principal_resolver()

    try:
        yield app
    finally:
        app.dependency_overrides.pop(get_session, None)
        settings_module.get_settings.cache_clear()


@pytest.fixture()
def realtime_client(realtime_app: FastAPI) -> TestClient:
    with TestClient(realtime_app) as client:
        yield client


def _build_websocket(headers: dict[str, str] | None = None) -> WebSocket:
    base_headers = [
        (b"host", b"testserver"),
        (b"connection", b"upgrade"),
        (b"upgrade", b"websocket"),
        (b"sec-websocket-version", b"13"),
        (b"sec-websocket-key", b"testing"),
    ]
    if headers:
        base_headers.extend(
            (name.lower().encode("latin-1"), value.encode("latin-1"))
            for name, value in headers.items()
        )

    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "scheme": "ws",
        "path": "/realtime/notebooks/example",
        "raw_path": b"/realtime/notebooks/example",
        "query_string": b"",
        "headers": base_headers,
        "client": ("testclient", 12345),
        "server": ("testserver", 80),
        "subprotocols": [],
        "extensions": {"websocket.http.response": {}},
    }

    async def _receive() -> dict[str, object]:  # pragma: no cover - unused in tests
        return {"type": "websocket.disconnect"}

    async def _send(_message: dict[str, object]) -> None:  # pragma: no cover - unused
        return None

    return WebSocket(scope, _receive, _send)


@pytest.mark.no_auth_override
def test_realtime_poll_requires_authentication(realtime_client: TestClient) -> None:
    response = realtime_client.get("/realtime/notebooks/example/poll")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.no_auth_override
async def test_realtime_websocket_requires_authentication(
    realtime_app: FastAPI,
) -> None:
    async with realtime_app.router.lifespan_context(realtime_app):
        websocket = _build_websocket()
        with pytest.raises(HTTPException) as exc:
            result = realtime.require_websocket_principal(websocket)
            if isawaitable(result):
                await result

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.no_auth_override
async def test_realtime_websocket_denies_forbidden_access(
    realtime_app: FastAPI, monkeypatch: pytest.MonkeyPatch
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

    async with realtime_app.router.lifespan_context(realtime_app):
        websocket = _build_websocket(headers={"X-API-Key": "pytest-default-key"})
        principal_result = realtime.require_websocket_principal(websocket)
        principal = (
            await principal_result
            if isawaitable(principal_result)
            else principal_result
        )

        with pytest.raises(HTTPException) as exc:
            await realtime.notebook_updates(
                websocket,
                "example",
                session=object(),
                principal=principal,
            )

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
