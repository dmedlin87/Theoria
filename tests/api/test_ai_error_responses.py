import pytest
from fastapi.testclient import TestClient
from theo.services.api.app.models.ai import (
    CHAT_SESSION_TOTAL_CHAR_BUDGET,
    MAX_CHAT_MESSAGE_CONTENT_LENGTH,
)


@pytest.fixture
def client(api_test_client: TestClient) -> TestClient:
    return api_test_client


def test_chat_turn_empty_messages_returns_structured_error(client: TestClient) -> None:
    response = client.post("/ai/chat", json={"messages": []})

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "messages cannot be empty"
    assert payload["error"]["code"] == "AI_CHAT_EMPTY_MESSAGES"
    assert payload["error"]["severity"] == "user"


def test_chat_turn_missing_user_message_returns_structured_error(
    client: TestClient,
) -> None:
    response = client.post(
        "/ai/chat",
        json={
            "messages": [
                {"role": "assistant", "content": "Here's an answer."},
                {"role": "system", "content": "System instructions."},
            ]
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "missing user message"
    assert payload["error"]["code"] == "AI_CHAT_MISSING_USER_MESSAGE"
    assert payload["error"]["severity"] == "user"


def test_chat_turn_blank_user_message_returns_structured_error(client: TestClient) -> None:
    response = client.post(
        "/ai/chat",
        json={
            "messages": [
                {"role": "assistant", "content": "Previous answer."},
                {"role": "user", "content": "   \t"},
            ]
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "user message cannot be blank"
    assert payload["error"]["code"] == "AI_CHAT_EMPTY_USER_MESSAGE"
    assert payload["error"]["severity"] == "user"


def test_chat_turn_payload_too_large_returns_structured_error(client: TestClient) -> None:
    oversized_message = "x" * MAX_CHAT_MESSAGE_CONTENT_LENGTH
    # Add a safety margin to account for JSON structure overhead
    messages_needed = (CHAT_SESSION_TOTAL_CHAR_BUDGET // MAX_CHAT_MESSAGE_CONTENT_LENGTH) + 3
    response = client.post(
        "/ai/chat",
        json={
            "messages": [
                {"role": "user", "content": oversized_message}
                for _ in range(messages_needed)
            ]
        },
    )

    assert response.status_code == 413
    payload = response.json()
    assert payload["detail"] == "chat payload exceeds size limit"
    assert payload["error"]["code"] == "AI_CHAT_PAYLOAD_TOO_LARGE"
    assert payload["error"]["severity"] == "user"
