from __future__ import annotations

import logging
import socket
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
from theo.services.api.app.ingest import pipeline as pipeline_module  # noqa: E402


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


 
class _FakeHeaders(dict):
    def get_content_charset(self, default: str | None = None) -> str | None:
        return self.get("charset", default)
 
_PDF_EXTRACTION_ERROR = (
    "Unable to extract text from PDF; the file may be password protected or corrupted."
)
 


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



def test_ingest_url_allows_http(monkeypatch: pytest.MonkeyPatch, api_client: TestClient) -> None:
    captured: dict[str, str] = {}

    def fake_pipeline(session, url: str, **kwargs):  # noqa: ANN001
        captured["url"] = url
        return _mkdoc()

    monkeypatch.setattr(ingest_module, "run_pipeline_for_url", fake_pipeline)

    response = api_client.post("/ingest/url", json={"url": "https://example.com"})

    assert response.status_code == status.HTTP_200_OK
    assert captured["url"] == "https://example.com"


@pytest.mark.parametrize(
    "disallowed_url",
    [
        "file:///etc/passwd",
        "gopher://example.com/resource",
    ],
)
def test_ingest_url_rejects_disallowed_scheme(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient, disallowed_url: str
) -> None:
    def fail_pipeline(*args, **kwargs):  # noqa: ANN001 - simple assertion helper
        raise AssertionError("URL validation should prevent pipeline execution")

    monkeypatch.setattr(ingest_module, "run_pipeline_for_url", fail_pipeline)

    response = api_client.post("/ingest/url", json={"url": disallowed_url})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    "blocked_url",
    [
        "http://localhost/resource",
        "http://127.0.0.1/secret",
        "http://192.168.1.10/internal",
    ],
)
def test_ingest_url_blocks_private_targets(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient, blocked_url: str
) -> None:
    from theo.services.api.app.ingest import pipeline as pipeline_module

    def unexpected_fetch(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("Disallowed URLs must not be fetched")

    monkeypatch.setattr(pipeline_module, "_fetch_web_document", unexpected_fetch)

    response = api_client.post("/ingest/url", json={"url": blocked_url})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "URL target is not allowed for ingestion"



def _install_url_pipeline_stub(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    opener_factory,
    *,
    expected_failure_message: str,
) -> None:
    monkeypatch.setattr(pipeline_module, "build_opener", opener_factory)

    def _fake_run(session, url: str, source_type=None, frontmatter=None):  # noqa: ANN001
        with pytest.raises(
            pipeline_module.UnsupportedSourceError,
            match=expected_failure_message,
        ):
            pipeline_module._fetch_web_document(settings, url)
        raise pipeline_module.UnsupportedSourceError(expected_failure_message)

    monkeypatch.setattr(ingest_module, "run_pipeline_for_url", _fake_run)


def test_ingest_url_times_out_on_slow_response(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    settings = Settings()
    settings.ingest_web_timeout_seconds = 0.5
    settings.ingest_web_max_bytes = 1024
    settings.ingest_web_max_redirects = 3

    class _TimeoutResponse:
        headers = _FakeHeaders()

        def geturl(self) -> str:
            return "https://slow.example.com"

        def read(self, size: int | None = None) -> bytes:  # noqa: ARG002
            raise socket.timeout()

        def close(self) -> None:
            pass

    class _TimeoutOpener:
        def __init__(self, handler):  # noqa: ANN001
            self.handler = handler
            self.addheaders = []

        def open(self, request, timeout=None):  # noqa: ANN001, D401
            return _TimeoutResponse()

    _install_url_pipeline_stub(
        monkeypatch,
        settings,
        lambda *handlers: _TimeoutOpener(handlers[0]),
        expected_failure_message="Fetching URL timed out after 0.5 seconds",
    )

    response = api_client.post("/ingest/url", json={"url": "https://slow.example.com"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Fetching URL timed out after 0.5 seconds"


def test_ingest_url_rejects_oversized_response(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    settings = Settings()
    settings.ingest_web_timeout_seconds = 1.0
    settings.ingest_web_max_bytes = 10
    settings.ingest_web_max_redirects = 3

    class _OversizedResponse:
        def __init__(self) -> None:
            self.headers = _FakeHeaders()
            self._chunks = [b"a" * 8, b"b" * 8, b""]

        def geturl(self) -> str:
            return "https://large.example.com"

        def read(self, size: int | None = None) -> bytes:  # noqa: ARG002
            return self._chunks.pop(0)

        def close(self) -> None:
            pass

    class _OversizedOpener:
        def __init__(self, handler):  # noqa: ANN001
            self.handler = handler
            self.addheaders = []

        def open(self, request, timeout=None):  # noqa: ANN001, D401
            return _OversizedResponse()

    _install_url_pipeline_stub(
        monkeypatch,
        settings,
        lambda *handlers: _OversizedOpener(handlers[0]),
        expected_failure_message=(
            "Fetched content exceeded maximum allowed size of 10 bytes"
        ),
    )

    response = api_client.post("/ingest/url", json={"url": "https://large.example.com"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.json()["detail"]
        == "Fetched content exceeded maximum allowed size of 10 bytes"
    )


def test_ingest_url_detects_redirect_loop(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    settings = Settings()
    settings.ingest_web_timeout_seconds = 1.0
    settings.ingest_web_max_bytes = 1024
    settings.ingest_web_max_redirects = 2

    class _RedirectResponse:
        def __init__(self, url: str, location: str) -> None:
            self._url = url
            self._code = 302
            self.headers = _FakeHeaders({"Location": location})

        def getcode(self) -> int:
            return self._code

        def geturl(self) -> str:
            return self._url

        def read(self, size: int | None = None) -> bytes:  # noqa: ARG002
            return b""

        def close(self) -> None:
            pass

    class _RedirectLoopOpener:
        def __init__(self, handler):  # noqa: ANN001
            self.handler = handler
            self.addheaders = []
            self._responses = [
                _RedirectResponse("https://loop.example.com", "https://loop.example.com/b"),
                _RedirectResponse("https://loop.example.com/b", "https://loop.example.com"),
            ]

        def open(self, request, timeout=None):  # noqa: ANN001, D401
            if not self._responses:
                raise RuntimeError("No more responses")

            response = self._responses.pop(0)
            if response.getcode() in {301, 302, 303, 307, 308}:
                new_request = self.handler.redirect_request(
                    request,
                    response,
                    response.getcode(),
                    "Found",
                    response.headers,
                    response.headers.get("Location"),
                )
                return self.open(new_request, timeout=timeout)
            return response

    _install_url_pipeline_stub(
        monkeypatch,
        settings,
        lambda *handlers: _RedirectLoopOpener(handlers[0]),
        expected_failure_message="URL redirect loop detected",
    )

    response = api_client.post("/ingest/url", json={"url": "https://loop.example.com"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "URL redirect loop detected"
 
def test_ingest_file_rejects_password_protected_pdf(api_client: TestClient) -> None:
    pdf_path = PROJECT_ROOT / "fixtures" / "pdf" / "password_protected.pdf"
    with pdf_path.open("rb") as handle:
        response = api_client.post(
            "/ingest/file",
            files={"file": (pdf_path.name, handle.read(), "application/pdf")},
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": _PDF_EXTRACTION_ERROR}


def test_ingest_file_rejects_corrupt_pdf(api_client: TestClient) -> None:
    pdf_path = PROJECT_ROOT / "fixtures" / "pdf" / "corrupt_sample.pdf"
    with pdf_path.open("rb") as handle:
        response = api_client.post(
            "/ingest/file",
            files={"file": (pdf_path.name, handle.read(), "application/pdf")},
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"detail": _PDF_EXTRACTION_ERROR}

 

