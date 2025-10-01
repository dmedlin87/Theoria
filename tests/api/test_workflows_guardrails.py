import pytest

from theo.services.api.app.ai.rag.guardrails import GuardrailError
from theo.services.api.app.ai.rag.models import RAGAnswer
from theo.services.api.app.models.search import HybridSearchFilters
from theo.services.api.app.routes.ai.workflows.guardrails import (
    build_guardrail_metadata,
    extract_refusal_text,
    guardrail_advisory,
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

