"""Tests for API error payloads and responses."""

from __future__ import annotations

import json
from typing import Mapping

import pytest

from theo.services.api.app.errors import IngestionError, Severity, TheoError


@pytest.mark.parametrize(
    "hint,data,trace_id",
    [
        (None, None, None),
        ("Check your input", None, None),
        (None, {"foo": "bar"}, "trace-123"),
        ("Retry", {"attempt": 2}, "trace-456"),
    ],
)
def test_theo_error_to_payload_combinations(
    hint: str | None, data: Mapping[str, str] | None, trace_id: str | None
) -> None:
    error = TheoError(
        message="Something went wrong",
        code="E_GENERIC",
        status_code=400,
        hint=hint,
        data=data,
    )

    payload = error.to_payload(trace_id=trace_id)

    assert payload["error"]["code"] == "E_GENERIC"
    assert payload["error"]["message"] == "Something went wrong"
    assert payload["error"]["severity"] == Severity.CRITICAL.value
    assert payload["detail"] == "Something went wrong"

    if hint is None:
        assert "hint" not in payload["error"]
    else:
        assert payload["error"]["hint"] == hint

    if data is None:
        assert "data" not in payload["error"]
    else:
        assert payload["error"]["data"] == dict(data)

    if trace_id is None:
        assert "trace_id" not in payload
    else:
        assert payload["trace_id"] == trace_id


def test_error_to_response_uses_payload() -> None:
    error = IngestionError(
        message="Failed to process file",
        code="INGEST_FAILURE",
        status_code=503,
        hint="Try again later",
        data={"document_id": "doc-123"},
    )
    trace_id = "trace-response"

    expected_payload = error.to_payload(trace_id=trace_id)

    response = error.to_response(trace_id=trace_id)

    assert response.status_code == error.status_code
    assert json.loads(response.body) == expected_payload
