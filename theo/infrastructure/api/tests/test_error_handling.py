from __future__ import annotations

import io
import socket
from typing import Any

import pytest
from fastapi.testclient import TestClient

from theo.infrastructure.api.app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_ingest_invalid_frontmatter_returns_structured_error(client: TestClient) -> None:
    files = {"file": ("sample.txt", io.BytesIO(b"hello"), "text/plain")}
    response = client.post(
        "/ingest/file",
        files=files,
        data={"frontmatter": "{invalid"},
        headers={"x-trace-id": "trace-test-1"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "INGESTION_INVALID_FRONTMATTER"
    assert payload["error"]["severity"] == "user"
    assert payload["trace_id"] == "trace-test-1"


def test_document_not_found_uses_retrieval_error_envelope(client: TestClient) -> None:
    response = client.get(
        "/documents/nonexistent",
        headers={"x-trace-id": "trace-test-2"},
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "RETRIEVAL_DOCUMENT_NOT_FOUND"
    assert payload["error"]["severity"] == "user"
    assert payload["trace_id"] == "trace-test-2"


def test_ingest_url_failure_surfaces_resilience_metadata(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_reports: list[dict[str, Any]] = []

    def _capture_report(report, logger=None):  # type: ignore[no-untyped-def]
        captured_reports.append(report.context)

    monkeypatch.setattr(
        "theo.infrastructure.api.app.debug.middleware.emit_debug_report",
        _capture_report,
    )

    def _failing_fetch(*args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        raise socket.timeout("boom")

    monkeypatch.setattr(
        "theo.infrastructure.api.app.ingest.pipeline.fetch_web_document",
        _failing_fetch,
    )

    response = client.post(
        "/ingest/url",
        json={"url": "https://example.com", "source_type": "web_page"},
        headers={"x-trace-id": "trace-test-3"},
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload["error"]["code"] == "INGESTION_NETWORK_FAILURE"
    resilience = payload["error"]["data"]["resilience"]
    assert resilience["category"] == "timeout"

    assert captured_reports, "Expected debug report to be emitted"
    report_context = captured_reports[0]
    assert report_context.get("error_code") == "INGESTION_NETWORK_FAILURE"
    assert report_context.get("resilience", {}).get("category") == "timeout"
