from __future__ import annotations

import logging
from pathlib import Path
import sys

import pytest
from fastapi import status
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core.database import get_session  # noqa: E402
from theo.services.api.app.core.settings import Settings  # noqa: E402
from theo.services.api.app.main import app  # noqa: E402
from theo.services.api.app.routes import ingest as ingest_module  # noqa: E402


@pytest.fixture()
def api_client():
    def _override_session():
        yield object()

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


def _mkdoc(document_id: str = "doc"):
    class _Doc:
        id = document_id

    return _Doc()


def _override_ingest_limit(monkeypatch: pytest.MonkeyPatch, limit: int) -> Settings:
    settings = Settings()
    settings.ingest_upload_max_bytes = limit
    monkeypatch.setattr(ingest_module, "get_settings", lambda: settings)
    return settings


def test_ingest_file_streams_large_upload_without_buffering(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    _override_ingest_limit(monkeypatch, 12 * 1024 * 1024)

    captured_sizes: list[int] = []

    original_iter = ingest_module._iter_upload_chunks

    async def tracking_iter(upload, chunk_size=ingest_module._UPLOAD_CHUNK_SIZE):
        async for chunk in original_iter(upload, chunk_size=chunk_size):
            captured_sizes.append(len(chunk))
            yield chunk

    monkeypatch.setattr(ingest_module, "_iter_upload_chunks", tracking_iter)

    stored: dict[str, Path] = {}
    recorded_size: dict[str, int] = {}

    def fake_pipeline(_session, path: Path, frontmatter):
        stored["path"] = path
        recorded_size["bytes"] = path.stat().st_size
        return _mkdoc()

    monkeypatch.setattr(ingest_module, "run_pipeline_for_file", fake_pipeline)

    payload = b"x" * (11 * 1024 * 1024)

    response = api_client.post(
        "/ingest/file",
        files={"file": ("large.bin", payload, "application/octet-stream")},
    )

    assert response.status_code == 200
    assert "path" in stored
    assert recorded_size.get("bytes") == len(payload)
    assert sum(captured_sizes) == len(payload)
    assert max(captured_sizes) <= ingest_module._UPLOAD_CHUNK_SIZE
    assert len(captured_sizes) >= 2


def test_ingest_file_logs_large_body_as_truncated(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    _override_ingest_limit(monkeypatch, 12 * 1024 * 1024)

    def failing_pipeline(_session, path: Path, frontmatter):
        raise RuntimeError("boom")

    monkeypatch.setattr(ingest_module, "run_pipeline_for_file", failing_pipeline)

    payload = b"y" * (11 * 1024 * 1024)

    with caplog.at_level(logging.ERROR, logger="theo.api.errors"):
        response = api_client.post(
            "/ingest/file",
            files={"file": ("large.bin", payload, "application/octet-stream")},
        )

    assert response.status_code == 500
    debug_records = [record for record in caplog.records if record.getMessage() == "api.debug_report"]
    assert debug_records, "expected a debug report for the failure"
    debug_report = debug_records[0].__dict__["debug_report"]
    body = debug_report["request"].get("body")
    assert body is not None
    assert body["truncated"] is True
    assert body["bytes"] >= len(payload)
    assert len(body["preview"]) <= 2048


def test_ingest_file_rejects_upload_exceeding_limit(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    _override_ingest_limit(monkeypatch, 1 * 1024 * 1024)

    called = False

    def fake_pipeline(_session, path: Path, frontmatter):
        nonlocal called
        called = True
        return _mkdoc()

    monkeypatch.setattr(ingest_module, "run_pipeline_for_file", fake_pipeline)

    payload = b"z" * (2 * 1024 * 1024)

    response = api_client.post(
        "/ingest/file",
        files={"file": ("huge.bin", payload, "application/octet-stream")},
    )

    assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert called is False


