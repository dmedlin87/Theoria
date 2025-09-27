from __future__ import annotations

import logging
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

from theo.services.api.app.debug import ErrorReportingMiddleware, build_debug_report  # noqa: E402


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
    monkeypatch.setenv("SECRET_KEY", "hidden")
    body = b"{\"password\": \"secret\"}"
    request = _make_request(body)

    report = build_debug_report(request, exc=ValueError("boom"), body=body)
    payload = report.as_dict()

    assert payload["request"]["headers"] == {"x-request-id": "123", "cf-ipcountry": "US"}
    assert "authorization" not in payload["request"]["headers"]
    assert payload["request"]["body"]["bytes"] == len(body)
    assert payload["request"]["body"]["truncated"] is False

    assert payload["environment"] == {"THEO_VISIBLE": "1"}
    assert payload["error"]["type"] == "ValueError"
    assert "ValueError: boom" in "".join(payload["error"]["stacktrace"])


def test_error_reporting_middleware_emits_report(caplog: pytest.LogCaptureFixture) -> None:
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
