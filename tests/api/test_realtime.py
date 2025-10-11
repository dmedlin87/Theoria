import pytest

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
