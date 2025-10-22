from __future__ import annotations

from ipaddress import ip_address
from types import SimpleNamespace
from typing import Any, Callable

import pytest
from hypothesis import given, strategies as st

from theo.services.api.app.ingest import network
from theo.services.api.app.ingest.network import (
    LoopDetectingRedirectHandler,
    UnsupportedSourceError,
    _parse_blocked_networks,
    extract_youtube_video_id,
    fetch_web_document,
    is_youtube_url,
    normalise_host,
    resolve_host_addresses,
)


class _FakeSettings(SimpleNamespace):
    ingest_url_blocked_schemes: list[str] = []
    ingest_url_allowed_schemes: list[str] = ["http", "https"]
    ingest_url_allowed_hosts: list[str] = []
    ingest_url_blocked_hosts: list[str] = []
    ingest_url_blocked_ip_networks: list[str] = []
    ingest_url_block_private_networks: bool = True
    ingest_web_timeout_seconds: float = 1.0
    ingest_web_max_bytes: int | None = 512
    ingest_web_max_redirects: int = 3
    user_agent: str = "pytest-agent"


def _build_settings(**overrides: Any) -> _FakeSettings:
    data = {key: getattr(_FakeSettings, key) for key in _FakeSettings.__dict__ if not key.startswith("_")}
    data.update(overrides)
    return _FakeSettings(**data)


def test_normalise_host_strips_and_lowercases() -> None:
    assert normalise_host("  Example.COM.  ") == "example.com"


@given(st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_categories=("Cs",)), max_size=64))
def test_normalise_host_property(host: str) -> None:
    result = normalise_host(host)
    assert result == host.strip().lower().rstrip(".")
    assert normalise_host(result) == result


def test_resolve_host_addresses_uses_dns_and_deduplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_getaddrinfo(host: str, *_args: Any, **_kwargs: Any) -> list[tuple[Any, ...]]:
        calls.append(host)
        return [
            (None, None, None, None, ("93.184.216.34", 0)),
            (None, None, None, None, ("2606:2800:220:1:248:1893:25c8:1946", 0, 0, 0)),
            (None, None, None, None, ("93.184.216.34%eth0", 0)),
            (None, None, None, None, ("invalid", 0)),
        ]

    monkeypatch.setattr(network.socket, "getaddrinfo", fake_getaddrinfo)

    resolved = resolve_host_addresses("Example.COM")

    assert calls == ["example.com"]
    assert resolved == (
        ip_address("93.184.216.34"),
        ip_address("2606:2800:220:1:248:1893:25c8:1946"),
    )


def test_resolve_host_addresses_handles_dns_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(host: str, *_args: Any, **_kwargs: Any) -> list[tuple[Any, ...]]:
        raise network.socket.gaierror("boom")

    monkeypatch.setattr(network.socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(UnsupportedSourceError):
        resolve_host_addresses("unknown.local")


def test_ensure_resolved_addresses_allowed_rejects_private(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings(ingest_url_block_private_networks=True)

    with pytest.raises(UnsupportedSourceError):
        network.ensure_resolved_addresses_allowed(settings, (ip_address("127.0.0.1"),))


def test_ensure_resolved_addresses_allowed_rejects_blocked_cidr(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings(
        ingest_url_block_private_networks=False,
        ingest_url_blocked_ip_networks=["10.0.0.0/8", "invalid"],
    )

    blocked = _parse_blocked_networks(settings.ingest_url_blocked_ip_networks)
    assert any(str(net) == "10.0.0.0/8" for net in blocked)

    with pytest.raises(UnsupportedSourceError):
        network.ensure_resolved_addresses_allowed(settings, (ip_address("10.1.2.3"),))


def test_loop_detecting_redirect_handler_blocks_loops(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings(ingest_url_allowed_hosts=["example.com"])
    handler = LoopDetectingRedirectHandler(2, settings)
    handler.visited.add("https://example.com/start")

    redirects: list[str] = []

    def fake_ensure(settings_obj: Any, url: str) -> None:
        redirects.append(url)

    monkeypatch.setattr(network, "ensure_url_allowed", fake_ensure)

    def fake_super(self: Any, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        class _Redirected(SimpleNamespace):
            timeout: float | None = getattr(req, "timeout", None)

        return _Redirected()

    monkeypatch.setattr(
        network.HTTPRedirectHandler,
        "redirect_request",
        fake_super,
        raising=False,
    )

    class _Request(SimpleNamespace):
        def get_full_url(self) -> str:
            return self.full_url

    request = _Request(full_url="https://example.com/start", timeout=5.0)

    redirected = handler.redirect_request(
        request,
        fp=None,
        code=302,
        msg="Found",
        headers={"Location": "/next"},
        newurl="ignored",
    )

    assert redirects == ["https://example.com/next"]
    assert handler.redirect_count == 1
    assert isinstance(redirected, SimpleNamespace)

    with pytest.raises(UnsupportedSourceError):
        handler.redirect_request(
            request,
            fp=None,
            code=302,
            msg="Found",
            headers={"Location": "/next"},
            newurl="ignored",
        )


def test_loop_detecting_redirect_handler_requires_location() -> None:
    settings = _build_settings()
    handler = LoopDetectingRedirectHandler(1, settings)

    with pytest.raises(UnsupportedSourceError):
        handler.redirect_request(
            SimpleNamespace(full_url="https://example.com/start"),
            fp=None,
            code=301,
            msg="Moved",
            headers={},
            newurl="ignored",
        )


class _FakeHeaders(dict):
    def get_content_charset(self) -> str | None:  # pragma: no cover - simple passthrough
        return self.get("Content-Charset")


class _FakeResponse:
    def __init__(self, *, url: str, chunks: list[bytes], headers: dict[str, str] | None = None) -> None:
        self._url = url
        self._chunks = list(chunks)
        self._headers = _FakeHeaders(headers or {})
        self.closed = False

    @property
    def headers(self) -> _FakeHeaders:
        return self._headers

    def geturl(self) -> str:
        return self._url

    def read(self, _size: int) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""

    def close(self) -> None:
        self.closed = True


def _opener_factory(
    response_factory: Callable[[], _FakeResponse],
    expected_user_agent: str,
) -> Callable[[Any], Any]:
    def factory(handler: Any) -> Any:
        class _Opener:
            addheaders: list[tuple[str, str]] = []

            def open(self, request: Any, timeout: float) -> _FakeResponse:
                ua = request.get_header("User-agent")
                assert ua == expected_user_agent
                assert timeout > 0
                return response_factory()

        return _Opener()

    return factory


def test_fetch_web_document_enforces_max_bytes_from_header(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings(ingest_web_max_bytes=100)

    calls: list[str] = []

    def fake_ensure(_settings: Any, url: str) -> None:
        calls.append(url)

    monkeypatch.setattr(network, "ensure_url_allowed", fake_ensure)

    response = _FakeResponse(
        url="https://example.com/final",
        chunks=[b"Hello world"],
        headers={"Content-Length": "200"},
    )

    with pytest.raises(UnsupportedSourceError):
        fetch_web_document(
            settings,
            "https://example.com/start",
            opener_factory=_opener_factory(lambda: response, settings.user_agent),
        )

    assert calls == ["https://example.com/start", "https://example.com/final"]
    assert response.closed is True


def test_fetch_web_document_streaming_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings(ingest_web_max_bytes=5)

    monkeypatch.setattr(network, "ensure_url_allowed", lambda *_args, **_kwargs: None)

    response = _FakeResponse(
        url="https://example.com/final",
        chunks=[b"123", b"456", b""],
    )

    with pytest.raises(UnsupportedSourceError):
        fetch_web_document(
            settings,
            "https://example.com/start",
            opener_factory=_opener_factory(lambda: response, settings.user_agent),
        )

    assert response.closed is True


def test_fetch_web_document_returns_html_and_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings(ingest_web_max_bytes=None)

    monkeypatch.setattr(network, "ensure_url_allowed", lambda *_args, **_kwargs: None)

    html = """<html><head><title>Example</title><link rel='canonical' href='https://example.com/final'></head>\n<body>Hi</body></html>"""

    response = _FakeResponse(
        url="https://example.com/final",
        chunks=[html.encode()],
        headers={"Content-Charset": "utf-8"},
    )

    document, metadata = fetch_web_document(
        settings,
        "https://example.com/start",
        opener_factory=_opener_factory(lambda: response, settings.user_agent),
    )

    assert "Example" in document
    assert metadata["final_url"] == "https://example.com/final"
    assert metadata["canonical_url"] == "https://example.com/final"
    assert metadata["source_url"] == "https://example.com/final"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=abc123", "abc123"),
        ("https://youtu.be/xyz789", "xyz789"),
        ("https://m.youtube.com/shorts/clip456", "clip456"),
        ("https://www.youtube.com/embed/clip999", "clip999"),
        ("https://www.youtube.com/v/legacy-id", "v/legacy-id"),
    ],
)
def test_extract_youtube_video_id_success(url: str, expected: str) -> None:
    assert extract_youtube_video_id(url) == expected


def test_extract_youtube_video_id_rejects_unknown() -> None:
    with pytest.raises(UnsupportedSourceError):
        extract_youtube_video_id("https://example.com/watch?v=abc123")


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=abc", True),
        ("https://youtu.be/abc", True),
        ("https://sub.youtube.com/watch?v=abc", True),
        ("https://example.com/watch?v=abc", False),
    ],
)
def test_is_youtube_url(url: str, expected: bool) -> None:
    assert is_youtube_url(url) is expected

