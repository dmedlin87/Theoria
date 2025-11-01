import json
from unittest.mock import MagicMock

import pytest

from theo.infrastructure.api.app.ai.rag.guardrails import GuardrailError
from theo.infrastructure.api.app.ai.rag.models import RAGAnswer
from theo.infrastructure.api.app.models.search import HybridSearchFilters
from theo.infrastructure.api.app.routes.ai.workflows.guardrails import (
    build_guardrail_metadata,
    extract_refusal_text,
    guardrail_advisory,
    guardrail_http_exception,
)


def test_extract_refusal_text_strips_sources_block() -> None:
    answer = RAGAnswer(
        summary="",
        citations=[],
        model_output="Refusal message. Sources: 1. Example",
    )
    assert extract_refusal_text(answer) == "Refusal message."


@pytest.mark.parametrize(
    "metadata,expected_action",
    [
        ({"guardrail": "ingest", "suggested_action": "upload"}, "upload"),
        ({"guardrail": "retrieval", "suggested_action": "unknown"}, "search"),
    ],
)
def test_build_guardrail_metadata_normalises_payload(metadata: dict[str, str], expected_action: str) -> None:
    filters = HybridSearchFilters(collection="Alpha")
    error = GuardrailError("blocked", metadata={**metadata, "filters": {"collection": "Alpha"}})
    result = build_guardrail_metadata(error, filters)
    assert result.suggested_action == expected_action
    assert result.guardrail in {"ingest", "retrieval", "unknown"}
    assert result.filters is not None
    assert result.filters.collection == "Alpha"


def test_guardrail_advisory_generates_search_suggestion() -> None:
    metadata = build_guardrail_metadata(GuardrailError("blocked"), None)
    advisory = guardrail_advisory(
        "Refusal",
        question="What now?",
        osis="John.1.1",
        filters=None,
        metadata=metadata,
    )
    assert advisory.message == "Refusal"
    assert advisory.suggestions
    assert advisory.suggestions[0].action == "search"


def test_guardrail_http_exception_embeds_error_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()
    fake_answer = RAGAnswer(summary="Refused", citations=[])

    monkeypatch.setattr(
        "theo.infrastructure.api.app.routes.ai.workflows.guardrails.build_guardrail_refusal",
        lambda _session, reason=None: fake_answer,
    )

    error = GuardrailError(
        "Blocked",
        metadata={
            "code": "guardrail_profile_no_match",
            "guardrail": "retrieval",
            "suggested_action": "upload",
            "reason": "No passages matched",
            "filters": {"collection": "Alpha"},
        },
    )

    filters = HybridSearchFilters(collection="Alpha")
    response = guardrail_http_exception(
        error,
        session=session,
        question="What is hope?",
        osis="John.1.1",
        filters=filters,
    )

    payload = json.loads(response.body)
    assert payload["error"]["code"] == "AI_GUARDRAIL_PROFILE_NO_MATCH"
    assert payload["detail"]["type"] == "guardrail_refusal"
    assert payload["error"]["data"]["guardrail"] == "retrieval"
    assert payload["error"]["data"]["filters"]["collection"] == "Alpha"


@pytest.mark.parametrize("action", ["retry", "none"])
def test_guardrail_advisory_supports_retry_and_cancellation(action: str) -> None:
    error = GuardrailError(
        "Blocked",
        metadata={"guardrail": "generation", "suggested_action": action},
    )
    metadata = build_guardrail_metadata(error, None)

    advisory = guardrail_advisory(
        "Please adjust your request",
        question="Should we try again?",
        osis=None,
        filters=None,
        metadata=metadata,
    )

    assert advisory.metadata is not None
    assert advisory.metadata.suggested_action == action
    assert advisory.suggestions, "Search follow-up should be available"
    assert advisory.suggestions[0].action == "search"


def test_guardrail_http_exception_marks_safe_refusals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()
    fake_answer = RAGAnswer(summary="Refused", citations=[])

    monkeypatch.setattr(
        "theo.infrastructure.api.app.routes.ai.workflows.guardrails.build_guardrail_refusal",
        lambda _session, reason=None: fake_answer,
    )

    error = GuardrailError(
        "Request cancelled",
        metadata={
            "guardrail": "generation",
            "suggested_action": "retry",
            "reason": "User cancelled",
        },
    )
    setattr(error, "safe_refusal", True)

    response = guardrail_http_exception(
        error,
        session=session,
        question="Should I continue?",
        osis=None,
        filters=None,
    )

    payload = json.loads(response.body)
    assert payload["error"]["data"]["safe_refusal"] is True
    assert payload["error"]["data"]["reason"] == "User cancelled"
    assert payload["guardrail_advisory"]["metadata"]["suggested_action"] == "retry"


def test_guardrail_http_exception_handles_invalid_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()
    fake_answer = RAGAnswer(summary="Refused", citations=[])

    monkeypatch.setattr(
        "theo.infrastructure.api.app.routes.ai.workflows.guardrails.build_guardrail_refusal",
        lambda _session, reason=None: fake_answer,
    )

    error = GuardrailError("Invalid payload", metadata="not-a-mapping")

    response = guardrail_http_exception(
        error,
        session=session,
        question="What happened?",
        osis=None,
        filters=None,
    )

    payload = json.loads(response.body)
    assert payload["error"]["data"]["guardrail"] == "unknown"
    assert payload["guardrail_advisory"]["metadata"]["suggested_action"] == "search"

