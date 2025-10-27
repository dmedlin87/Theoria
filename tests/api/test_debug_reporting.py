from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.requests import Request
from starlette.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.infrastructure.api.app.debug import (  # noqa: E402
    ErrorReportingMiddleware,
    build_debug_report,
    emit_debug_report,
)


async def _receive_with_body(body: bytes) -> Dict[str, Any]:
    return {"type": "http.request", "body": body, "more_body": False}


def _make_request(body: bytes) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/example",
        "root_path": "",
        "scheme": "http",
        "headers": [
            (b"x-request-id", b"123"),
            (b"authorization", b"secret"),
            (b"cf-ipcountry", b"US"),
        ],
        "query_string": b"foo=bar",
        "client": ("127.0.0.1", 4321),
        "server": ("testserver", 80),
    }
    return Request(scope, lambda: _receive_with_body(body))


def test_build_debug_report_filters_sensitive_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("THEO_VISIBLE", "1")
    monkeypatch.setenv("THEO_PUBLIC_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("THEO_SECRET_KEY", "hidden")
    monkeypatch.setenv("THEO_ACCESS_TOKEN", "token")

    # Normalise the environment so we only assert on the keys we control.
    for key in list(os.environ):
        if key.startswith("THEO_") and key not in {"THEO_VISIBLE", "THEO_PUBLIC_ENDPOINT"}:
            monkeypatch.delenv(key, raising=False)
    body = b"{\"password\": \"secret\"}"
    request = _make_request(body)

    report = build_debug_report(request, exc=ValueError("boom"), body=body)
    payload = report.as_dict()

    assert payload["request"]["headers"] == {"x-request-id": "123", "cf-ipcountry": "US"}
    assert "authorization" not in payload["request"]["headers"]
    assert payload["request"]["body"]["bytes"] == len(body)
    assert payload["request"]["body"]["truncated"] is False

    environment = payload["environment"]
    assert environment["THEO_VISIBLE"] == "1"
    assert environment["THEO_PUBLIC_ENDPOINT"] == "https://example.invalid"
    assert "THEO_SECRET_KEY" not in environment
    assert "THEO_ACCESS_TOKEN" not in environment
    assert payload["error"]["type"] == "ValueError"
    assert "ValueError: boom" in "".join(payload["error"]["stacktrace"])


def test_error_reporting_middleware_emits_report(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("THEO_VISIBLE", "1")
    monkeypatch.setenv("THEO_SECRET_KEY", "hidden")

    app = FastAPI()
    app.add_middleware(
        ErrorReportingMiddleware,
        response_on_error=True,
        extra_context={"feature": "test"},
    )

    @app.get("/explode")
    def explode() -> None:
        raise RuntimeError("kaboom")

    client = TestClient(app)

    with caplog.at_level(logging.ERROR, logger="theo.api.errors"):
        response = client.get("/explode")

    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Internal Server Error"
    assert "debug_report_id" in data

    debug_records = [record for record in caplog.records if record.getMessage() == "api.debug_report"]
    assert debug_records, "expected a debug report log entry"
    logged_report = debug_records[0].__dict__["debug_report"]
    assert logged_report["context"]["feature"] == "test"
    assert logged_report["error"]["message"] == "kaboom"
    assert logged_report["environment"]["THEO_VISIBLE"] == "1"
    assert "THEO_SECRET_KEY" not in logged_report["environment"]


def test_debug_report_includes_trace_id(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    trace_id = "1234567890abcdef1234567890abcdef"
    monkeypatch.setattr(
        "theo.infrastructure.api.app.debug.reporting.get_current_trace_id", lambda: trace_id
    )

    request = _make_request(b"{}")
    report = build_debug_report(request, exc=None, body=None)
    assert report.context["trace_id"] == trace_id

    with caplog.at_level(logging.ERROR, logger="theo.api.errors"):
        emit_debug_report(report)

    debug_records = [record for record in caplog.records if record.getMessage() == "api.debug_report"]
    assert debug_records
    record = debug_records[0]
    assert getattr(record, "trace_id", None) == trace_id
