import pytest
from fastapi.testclient import TestClient

from theo.services.api.app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_chat_turn_empty_messages_returns_structured_error(client: TestClient) -> None:
    response = client.post("/ai/chat", json={"messages": []})

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "messages cannot be empty"
    assert payload["error"]["code"] == "AI_CHAT_EMPTY_MESSAGES"
    assert payload["error"]["severity"] == "user"
