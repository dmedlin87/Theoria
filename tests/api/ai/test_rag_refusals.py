"""Regression tests for guardrail refusal helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from theo.services.api.app.ai.rag.refusals import (
    REFUSAL_MESSAGE,
    REFUSAL_MODEL_NAME,
    _REFUSAL_FALLBACK_ANCHOR,
    _REFUSAL_FALLBACK_SNIPPET,
    _REFUSAL_FALLBACK_TITLE,
    build_guardrail_refusal,
)
from theo.services.api.app.persistence_models import Document, Passage


@dataclass(slots=True)
class _DummyResult:
    """Lightweight stand-in for SQLAlchemy result objects used in tests."""

    record: Any

    def first(self) -> Any:
        return self.record


class _DummySession:
    """Stubbed session that returns pre-configured query results."""

    def __init__(self, *, record: Any = None, raise_error: bool = False) -> None:
        self._record = record
        self._raise_error = raise_error
        self.executed_queries: list[Any] = []

    def execute(self, query: Any, *args: Any, **kwargs: Any) -> _DummyResult:
        self.executed_queries.append(query)
        if self._raise_error:
            raise RuntimeError("database unavailable")
        return _DummyResult(self._record)


@pytest.mark.parametrize(
    "dummy_session",
    [
        _DummySession(),
        _DummySession(raise_error=True),
    ],
)
def test_build_guardrail_refusal_uses_fallbacks_when_reference_missing(
    dummy_session: _DummySession,
) -> None:
    """When no database reference is available, the static fallback is returned."""

    answer = build_guardrail_refusal(dummy_session)

    assert answer.summary == REFUSAL_MESSAGE
    assert answer.model_name == REFUSAL_MODEL_NAME

    citation = answer.citations[0]
    assert citation.document_title == _REFUSAL_FALLBACK_TITLE
    assert citation.anchor == _REFUSAL_FALLBACK_ANCHOR
    assert citation.snippet == _REFUSAL_FALLBACK_SNIPPET
    assert citation.document_id == "guardrail-document"
    assert citation.passage_id == "guardrail-passage"

    assert answer.guardrail_profile == {"status": "refused"}
    assert answer.model_output.endswith(
        f"Sources: [1] {citation.osis} ({citation.anchor})"
    )


def test_build_guardrail_refusal_includes_reason_when_provided() -> None:
    """Optional guardrail reasons propagate into the refusal profile."""

    session = _DummySession()

    answer = build_guardrail_refusal(session, reason="policy_violation")

    assert answer.guardrail_profile == {
        "status": "refused",
        "reason": "policy_violation",
    }


def test_build_guardrail_refusal_uses_database_reference_when_available() -> None:
    """The refusal helper should synthesise a citation from stored passages."""

    passage = Passage(
        id="passage-001",
        document_id="doc-123",
        text="In the beginning was the Word, and the Word was with God.",
        osis_ref="John.1.1",
        start_char=0,
        end_char=56,
    )
    document = Document(
        id="doc-123",
        title="Gospel of John",
    )
    session = _DummySession(record=(passage, document))

    answer = build_guardrail_refusal(session)

    citation = answer.citations[0]
    assert citation.document_title == "Gospel of John"
    assert citation.document_id == "doc-123"
    assert citation.passage_id == "passage-001"
    assert citation.osis == "John.1.1"
    assert "Sources: [1] John.1.1" in answer.model_output
    # ensure fallback strings are not used when the database provides data
    assert citation.snippet != _REFUSAL_FALLBACK_SNIPPET
    assert citation.anchor != _REFUSAL_FALLBACK_ANCHOR

