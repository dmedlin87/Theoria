from __future__ import annotations

import logging
import socket
from pathlib import Path
import sys
from ipaddress import ip_address
from urllib.error import ContentTooShortError

import pytest
from fastapi import status
import json

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades.database import get_session  # noqa: E402
from theo.application.facades.settings import Settings  # noqa: E402
from theo.services.api.app.main import app  # noqa: E402
from theo.services.api.app.routes import ingest as ingest_module  # noqa: E402
from theo.services.api.app.services import ingestion_service as ingestion_service_module  # noqa: E402
from theo.services.api.app.ingest import pipeline as pipeline_module  # noqa: E402
from theo.services.api.app.ingest import network as network_module  # noqa: E402

PAYLOAD_TOO_LARGE = getattr(
    status, "HTTP_413_CONTENT_TOO_LARGE", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
)

@pytest.fixture()
def api_client(api_engine):
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


def _stub_address_resolution(monkeypatch: pytest.MonkeyPatch, address: str = "203.0.113.10") -> None:
    fake_addresses = (ip_address(address),)

    monkeypatch.setattr(
        network_module,
        "resolve_host_addresses",
        lambda host: fake_addresses,
    )
    monkeypatch.setattr(
        network_module,
        "ensure_resolved_addresses_allowed",
        lambda _settings, _addresses: None,
    )


def test_ensure_url_allowed_blocks_normalised_blocklist(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings()
    settings.ingest_url_block_private_networks = False
    settings.ingest_url_allowed_hosts = []
    settings.ingest_url_blocked_hosts = [" Example.COM "]

    _stub_address_resolution(monkeypatch)

    with pytest.raises(network_module.UnsupportedSourceError):
        network_module.ensure_url_allowed(settings, "https://EXAMPLE.com./path")


def test_ensure_url_allowed_respects_normalised_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings()
    settings.ingest_url_block_private_networks = False
    settings.ingest_url_allowed_hosts = [" Example.COM "]
    settings.ingest_url_blocked_hosts = ["blocked.example"]

    _stub_address_resolution(monkeypatch)

    # Should not raise when host is present in the allowlist after normalisation.
    network_module.ensure_url_allowed(settings, "https://example.com/resource")


def test_pipeline_allowlist_bypasses_private_network(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings()
    settings.ingest_url_block_private_networks = True
    settings.ingest_url_allowed_hosts = ["allowed.example"]

    def failing_url_check(_settings, _url):
        raise pipeline_module.UnsupportedSourceError("private network disallowed")

    monkeypatch.setattr(network_module, "ensure_url_allowed", failing_url_check)
    monkeypatch.setattr(
        pipeline_module,
        "_resolve_host_addresses",
        lambda _host: (ip_address("10.0.0.5"),),
    )

    # The pipeline fallback should treat allow-listed hosts as trusted even when
    # they resolve to private addresses.
    pipeline_module.ensure_url_allowed(settings, "https://allowed.example/doc")


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

    def fake_pipeline(
        _session, path: Path, frontmatter, *, dependencies=None
    ) -> object:
        stored["path"] = path
        recorded_size["bytes"] = path.stat().st_size
        return _mkdoc()

    monkeypatch.setattr(ingestion_service_module, "run_pipeline_for_file", fake_pipeline)

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

    def failing_pipeline(
        _session, path: Path, frontmatter, *, dependencies=None
    ) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(ingestion_service_module, "run_pipeline_for_file", failing_pipeline)

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

    def fake_pipeline(
        _session, path: Path, frontmatter, *, dependencies=None
    ) -> object:
        nonlocal called
        called = True
        return _mkdoc()

    monkeypatch.setattr(ingestion_service_module, "run_pipeline_for_file", fake_pipeline)

    payload = b"z" * (2 * 1024 * 1024)

    response = api_client.post(
        "/ingest/file",
        files={"file": ("huge.bin", payload, "application/octet-stream")},
    )

    assert response.status_code == PAYLOAD_TOO_LARGE
    assert called is False


def test_ingest_url_allows_http(monkeypatch: pytest.MonkeyPatch, api_client: TestClient) -> None:
    captured: dict[str, str] = {}

    def fake_pipeline(session, url: str, **kwargs):  # noqa: ANN001
        captured["url"] = url
        return _mkdoc()

    monkeypatch.setattr(ingestion_service_module, "run_pipeline_for_url", fake_pipeline)

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

    monkeypatch.setattr(ingestion_service_module, "run_pipeline_for_url", fail_pipeline)

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
    payload = response.json()
    assert payload.get("error", {}).get(
        "message"
    ) == "URL target is not allowed for ingestion"


def test_simple_ingest_streams_progress(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    items = [
        ingestion_service_module.cli_ingest.IngestItem(
            url="https://example.com/notes", source_type="web_page"
        ),
        ingestion_service_module.cli_ingest.IngestItem(
            url="https://example.org/docs", source_type="web_page"
        ),
    ]

    monkeypatch.setattr(
        ingestion_service_module.cli_ingest,
        "_discover_items",
        lambda sources, allowlist=None: items,
    )
    monkeypatch.setattr(
        ingestion_service_module.cli_ingest,
        "_batched",
        lambda iterable, size: iter([list(iterable)]),
    )

    captured_overrides: list[dict[str, object]] = []

    def fake_ingest(
        batch, overrides, post_batch_steps, *, dependencies=None
    ):  # noqa: ANN001 - test helper
        captured_overrides.append(dict(overrides))
        assert len(batch) == len(items)
        assert post_batch_steps == set()
        return [f"doc-{idx}" for idx, _ in enumerate(batch, start=1)]

    monkeypatch.setattr(
        ingestion_service_module.cli_ingest,
        "_ingest_batch_via_api",
        fake_ingest,
    )

    with api_client.stream(
        "POST",
        "/ingest/simple",
        json={
            "sources": ["https://example.com/seed"],
            "metadata": {"collection": "archive"},
        },
    ) as response:
        assert response.status_code == 200
        payload = [line for line in response.iter_lines() if line]

    events = [json.loads(line) for line in payload]
    event_names = [event.get("event") for event in events]
    assert "start" in event_names
    assert any(event.get("event") == "discovered" for event in events)
    assert "batch" in event_names
    assert "processed" in event_names
    assert event_names[-1] == "complete"
    assert captured_overrides == [
        {
            "collection": "archive",
            "author": ingestion_service_module.cli_ingest.DEFAULT_AUTHOR,
        }
    ]


def test_simple_ingest_rejects_bad_source(
    api_client: TestClient, tmp_path: Path
) -> None:
    settings = Settings()
    settings.simple_ingest_allowed_roots = [tmp_path]

    class _FailingCLI:
        def _discover_items(self, _sources, allowlist=None):  # noqa: ANN001 - helper
            raise ValueError("Path 'missing' does not exist")

    custom_service = ingestion_service_module.IngestionService(
        settings=settings,
        run_file_pipeline=ingestion_service_module.run_pipeline_for_file,
        run_url_pipeline=ingestion_service_module.run_pipeline_for_url,
        run_transcript_pipeline=ingestion_service_module.run_pipeline_for_transcript,
        cli_module=_FailingCLI(),
        log_workflow=lambda *a, **k: None,
    )

    app.dependency_overrides[
        ingestion_service_module.get_ingestion_service
    ] = lambda: custom_service

    try:
        response = api_client.post("/ingest/simple", json={"sources": ["missing"]})
    finally:
        app.dependency_overrides.pop(
            ingestion_service_module.get_ingestion_service, None
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload = response.json()
    assert payload.get("error", {}).get("message")
    assert "does not exist" in payload["error"]["message"]


def test_simple_ingest_allows_remote_sources_without_allowlist(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    settings = Settings()
    settings.simple_ingest_allowed_roots = []
    monkeypatch.setattr(ingest_module, "get_settings", lambda: settings)

    custom_service = ingestion_service_module.IngestionService(
        settings=settings,
        run_file_pipeline=ingestion_service_module.run_pipeline_for_file,
        run_url_pipeline=ingestion_service_module.run_pipeline_for_url,
        run_transcript_pipeline=ingestion_service_module.run_pipeline_for_transcript,
        cli_module=ingestion_service_module.cli_ingest,
        log_workflow=lambda *a, **k: None,
    )
    app.dependency_overrides[
        ingestion_service_module.get_ingestion_service
    ] = lambda: custom_service

    def fake_ingest(
        batch, overrides, post_batch_steps, *, dependencies=None
    ):  # noqa: ANN001 - test helper
        assert all(item.is_remote for item in batch)
        return ["doc-1"]

    monkeypatch.setattr(
        ingestion_service_module.cli_ingest,
        "_ingest_batch_via_api",
        fake_ingest,
    )

    try:
        with api_client.stream(
            "POST",
            "/ingest/simple",
            json={"sources": ["https://example.com/seed"]},
        ) as response:
            assert response.status_code == status.HTTP_200_OK
            payload = [line for line in response.iter_lines() if line]
    finally:
        app.dependency_overrides.pop(
            ingestion_service_module.get_ingestion_service, None
        )

    events = [json.loads(line) for line in payload]
    assert any(event.get("event") == "processed" for event in events)
    assert all(
        event.get("remote") is True
        for event in events
        if event.get("event") == "discovered"
    )


def test_simple_ingest_rejects_local_sources_without_allowlist(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient, tmp_path: Path
) -> None:
    local_file = tmp_path / "note.txt"
    local_file.write_text("content", encoding="utf-8")

    settings = Settings()
    settings.simple_ingest_allowed_roots = []
    monkeypatch.setattr(ingest_module, "get_settings", lambda: settings)

    response = api_client.post(
        "/ingest/simple",
        json={"sources": [str(local_file)]},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload = response.json()
    assert payload.get("error", {}).get("code") == "INGESTION_LOCAL_SOURCES_DISABLED"
    assert "Local ingestion is disabled" in payload["error"]["message"]


def test_simple_ingest_allows_sources_under_configured_roots(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient, tmp_path: Path
) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    allowed_file = allowed_root / "note.txt"
    allowed_file.write_text("content", encoding="utf-8")

    settings = Settings()
    settings.simple_ingest_allowed_roots = [allowed_root]
    monkeypatch.setattr(ingest_module, "get_settings", lambda: settings)

    custom_service = ingestion_service_module.IngestionService(
        settings=settings,
        run_file_pipeline=ingestion_service_module.run_pipeline_for_file,
        run_url_pipeline=ingestion_service_module.run_pipeline_for_url,
        run_transcript_pipeline=ingestion_service_module.run_pipeline_for_transcript,
        cli_module=ingestion_service_module.cli_ingest,
        log_workflow=lambda *a, **k: None,
    )
    app.dependency_overrides[
        ingestion_service_module.get_ingestion_service
    ] = lambda: custom_service

    def fake_ingest(
        batch, overrides, post_batch_steps, *, dependencies=None
    ):  # noqa: ANN001 - test helper
        assert len(batch) == 1
        return ["doc-1"]

    monkeypatch.setattr(
        ingestion_service_module.cli_ingest,
        "_ingest_batch_via_api",
        fake_ingest,
    )

    try:
        with api_client.stream(
            "POST",
            "/ingest/simple",
            json={"sources": [str(allowed_file)]},
        ) as response:
            assert response.status_code == status.HTTP_200_OK
            payload = [line for line in response.iter_lines() if line]
    finally:
        app.dependency_overrides.pop(
            ingestion_service_module.get_ingestion_service, None
        )

    events = [json.loads(line) for line in payload]
    assert any(event.get("event") == "processed" for event in events)


def test_simple_ingest_rejects_sources_outside_allowlist(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient, tmp_path: Path
) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    forbidden_root = tmp_path / "forbidden"
    forbidden_root.mkdir()
    forbidden_file = forbidden_root / "note.txt"
    forbidden_file.write_text("secret", encoding="utf-8")

    settings = Settings()
    settings.simple_ingest_allowed_roots = [allowed_root]
    monkeypatch.setattr(ingest_module, "get_settings", lambda: settings)

    custom_service = ingestion_service_module.IngestionService(
        settings=settings,
        run_file_pipeline=ingestion_service_module.run_pipeline_for_file,
        run_url_pipeline=ingestion_service_module.run_pipeline_for_url,
        run_transcript_pipeline=ingestion_service_module.run_pipeline_for_transcript,
        cli_module=ingestion_service_module.cli_ingest,
        log_workflow=lambda *a, **k: None,
    )
    app.dependency_overrides[
        ingestion_service_module.get_ingestion_service
    ] = lambda: custom_service

    try:
        response = api_client.post(
            "/ingest/simple",
            json={"sources": [str(forbidden_file)]},
        )
    finally:
        app.dependency_overrides.pop(
            ingestion_service_module.get_ingestion_service, None
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload = response.json()
    assert payload.get("error", {}).get("message")
    assert "not within an allowed ingest root" in payload["error"]["message"]



def _install_url_pipeline_stub(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    opener_factory,
    *,
    expected_failure_message: str,
) -> dict[str, int]:
    monkeypatch.setattr(ingest_module, "get_settings", lambda: settings)
    monkeypatch.setattr(pipeline_module, "build_opener", opener_factory)
    _stub_address_resolution(monkeypatch)

    call_counter = {"count": 0}

    def _fake_run(
        session,
        url: str,
        source_type=None,
        frontmatter=None,
        *,
        dependencies=None,
    ):  # noqa: ANN001
        call_counter["count"] += 1
        try:
            pipeline_module._fetch_web_document(settings, url)
        except pipeline_module.UnsupportedSourceError as exc:
            assert str(exc) == expected_failure_message
            raise
        raise AssertionError("URL fetch unexpectedly succeeded")

    monkeypatch.setattr(ingestion_service_module, "run_pipeline_for_url", _fake_run)

    return call_counter


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

    call_counter = _install_url_pipeline_stub(
        monkeypatch,
        settings,
        lambda *handlers: _TimeoutOpener(handlers[0]),
        expected_failure_message="Fetching URL timed out after 0.5 seconds",
    )

    response = api_client.post("/ingest/url", json={"url": "https://slow.example.com"})
    if response.status_code != status.HTTP_400_BAD_REQUEST:
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload = response.json()
    assert payload.get("error", {}).get("code") == "INGESTION_UNSUPPORTED_SOURCE"
    assert (
        payload.get("error", {}).get("message")
        == "Fetching URL timed out after 0.5 seconds"
    )
    assert payload.get("error", {}).get("severity") == "user"
    assert (
        payload.get("error", {}).get("hint")
        == "Review the URL and ensure it meets ingestion requirements."
    )
    assert call_counter["count"] == 1


def test_ingest_url_rejects_oversized_response(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    settings = Settings()
    settings.ingest_web_timeout_seconds = 1.0
    settings.ingest_web_max_bytes = 10
    settings.ingest_web_max_redirects = 3

    class _OversizedResponse:
        def __init__(self) -> None:
            self.headers = _FakeHeaders({"Content-Length": "16"})
            self._read_called = False

        def geturl(self) -> str:
            return "https://large.example.com"

        def read(self, size: int | None = None) -> bytes:  # noqa: ARG002
            self._read_called = True
            raise AssertionError("Read should not be attempted when Content-Length exceeds limit")

        def close(self) -> None:
            pass

    class _OversizedOpener:
        def __init__(self, handler):  # noqa: ANN001
            self.handler = handler
            self.addheaders = []

        def open(self, request, timeout=None):  # noqa: ANN001, D401
            return _OversizedResponse()

    call_counter = _install_url_pipeline_stub(
        monkeypatch,
        settings,
        lambda *handlers: _OversizedOpener(handlers[0]),
        expected_failure_message=(
            "Fetched content exceeded maximum allowed size of 10 bytes"
        ),
    )

    response = api_client.post("/ingest/url", json={"url": "https://large.example.com"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload = response.json()
    assert payload.get("error", {}).get("code") == "INGESTION_UNSUPPORTED_SOURCE"
    assert (
        payload.get("error", {}).get("message")
        == "Fetched content exceeded maximum allowed size of 10 bytes"
    )
    assert payload.get("error", {}).get("severity") == "user"
    assert (
        payload.get("error", {}).get("hint")
        == "Review the URL and ensure it meets ingestion requirements."
    )
    assert call_counter["count"] == 1


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

    call_counter = _install_url_pipeline_stub(
        monkeypatch,
        settings,
        lambda *handlers: _RedirectLoopOpener(handlers[0]),
        expected_failure_message="URL redirect loop detected",
    )

    response = api_client.post("/ingest/url", json={"url": "https://loop.example.com"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload = response.json()
    assert payload.get("error", {}).get("code") == "INGESTION_UNSUPPORTED_SOURCE"
    assert payload.get("error", {}).get("message") == "URL redirect loop detected"
    assert payload.get("error", {}).get("severity") == "user"
    assert (
        payload.get("error", {}).get("hint")
        == "Review the URL and ensure it meets ingestion requirements."
    )
    assert call_counter["count"] == 1


def test_ingest_url_streams_enforce_byte_limit(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    settings = Settings()
    settings.ingest_web_timeout_seconds = 1.0
    settings.ingest_web_max_bytes = 10
    settings.ingest_web_max_redirects = 3

    class _StreamingResponse:
        def __init__(self) -> None:
            self.headers = _FakeHeaders()
            self._chunks = [b"a" * 6, b"b" * 6, b""]

        def geturl(self) -> str:
            return "https://stream.example.com"

        def read(self, size: int | None = None) -> bytes:  # noqa: ARG002
            if not self._chunks:
                return b""
            return self._chunks.pop(0)

        def close(self) -> None:
            pass

    class _StreamingOpener:
        def __init__(self, handler):  # noqa: ANN001
            self.handler = handler
            self.addheaders = []

        def open(self, request, timeout=None):  # noqa: ANN001, D401
            return _StreamingResponse()

    call_counter = _install_url_pipeline_stub(
        monkeypatch,
        settings,
        lambda *handlers: _StreamingOpener(handlers[0]),
        expected_failure_message=(
            "Fetched content exceeded maximum allowed size of 10 bytes"
        ),
    )

    response = api_client.post(
        "/ingest/url", json={"url": "https://stream.example.com"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload = response.json()
    assert payload.get("error", {}).get("code") == "INGESTION_UNSUPPORTED_SOURCE"
    assert (
        payload.get("error", {}).get("message")
        == "Fetched content exceeded maximum allowed size of 10 bytes"
    )
    assert payload.get("error", {}).get("severity") == "user"
    assert (
        payload.get("error", {}).get("hint")
        == "Review the URL and ensure it meets ingestion requirements."
    )
    assert call_counter["count"] == 1


def test_ingest_url_reports_incomplete_read(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    settings = Settings()
    settings.ingest_web_timeout_seconds = 1.0
    settings.ingest_web_max_bytes = 1024
    settings.ingest_web_max_redirects = 3

    class _PartialResponse:
        headers = _FakeHeaders()

        def __init__(self) -> None:
            self._called = False

        def geturl(self) -> str:
            return "https://partial.example.com"

        def read(self, size: int | None = None) -> bytes:  # noqa: ARG002
            if not self._called:
                self._called = True
                raise ContentTooShortError("partial", b"chunk")
            return b""

        def close(self) -> None:
            pass

    class _PartialOpener:
        def __init__(self, handler):  # noqa: ANN001
            self.handler = handler
            self.addheaders = []

        def open(self, request, timeout=None):  # noqa: ANN001, D401
            return _PartialResponse()

    call_counter = _install_url_pipeline_stub(
        monkeypatch,
        settings,
        lambda *handlers: _PartialOpener(handlers[0]),
        expected_failure_message=(
            "Network connection ended before the response completed"
        ),
    )

    response = api_client.post(
        "/ingest/url", json={"url": "https://partial.example.com"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    payload = response.json()
    assert payload.get("error", {}).get("code") == "INGESTION_UNSUPPORTED_SOURCE"
    assert (
        payload.get("error", {}).get("message")
        == "Network connection ended before the response completed"
    )
    assert payload.get("error", {}).get("severity") == "user"
    assert (
        payload.get("error", {}).get("hint")
        == "Review the URL and ensure it meets ingestion requirements."
    )
    assert call_counter["count"] == 1


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


def test_extract_youtube_video_id_handles_embed_urls() -> None:
    url = "https://www.youtube.com/embed/abc123XYZ?feature=share"
    assert network_module.extract_youtube_video_id(url) == "abc123XYZ"



