"""Compatibility promoter tests for chat model requests."""

import pytest

from theo.infrastructure.api.app.models.ai import (
    MAX_CHAT_MESSAGE_CONTENT_LENGTH,
    ChatSessionMessage,
    ChatSessionRequest,
    ModeAliasMixin,
)


def test_mode_alias_promoter_translates_mode_to_model() -> None:
    promoted = ModeAliasMixin._promote_mode_alias({"mode": "gpt-4o"})

    assert promoted["model"] == "gpt-4o"
    assert "mode" not in promoted


def test_chat_session_quality_gates_reject_invalid_mode() -> None:
    request = ChatSessionRequest(
        messages=[ChatSessionMessage(role="user", content="Hello")],
        mode_id="forbidden-mode",
    )

    with pytest.raises(ValueError, match="Unknown reasoning mode"):
        ChatSessionRequest._validate_reasoning_mode(request)


def test_chat_session_quality_gates_reject_long_messages() -> None:
    request = ChatSessionRequest(
        messages=[
            ChatSessionMessage(
                role="user",
                content="x" * (MAX_CHAT_MESSAGE_CONTENT_LENGTH + 1),
            )
        ]
    )

    with pytest.raises(ValueError, match="maximum allowed length"):
        ChatSessionRequest._enforce_message_lengths(request)
