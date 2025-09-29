"""Network helpers for ingestion."""

from __future__ import annotations

import json
import socket
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .exceptions import UnsupportedSourceError
from .parsers import parse_html_metadata

_WEB_FETCH_CHUNK_SIZE = 64 * 1024


def _normalise_host(host: str) -> str:
    return host.strip().lower().rstrip(".")


def _parse_blocked_networks(networks: list[str]) -> list[ip_network]:
    parsed: list[ip_network] = []
    for cidr in networks:
        try:
            parsed.append(ip_network(cidr, strict=False))
        except ValueError:
            continue
    return parsed


def ensure_url_allowed(settings, url: str) -> None:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise UnsupportedSourceError("URL must include a scheme and host")

    scheme = parsed.scheme.lower()
    blocked_schemes = {item.lower() for item in settings.ingest_url_blocked_schemes}
    if scheme in blocked_schemes:
        raise UnsupportedSourceError("URL scheme is not allowed for ingestion")

    allowed_schemes = {item.lower() for item in settings.ingest_url_allowed_schemes}
    if allowed_schemes and scheme not in allowed_schemes:
        raise UnsupportedSourceError("URL scheme is not allowed for ingestion")

    if parsed.username or parsed.password:
        raise UnsupportedSourceError("URL target is not allowed for ingestion")

    host = parsed.hostname
    if host is None:
        raise UnsupportedSourceError("URL must include a hostname")

    normalised_host = _normalise_host(host)
    allowed_hosts = {item.lower() for item in settings.ingest_url_allowed_hosts}
    blocked_hosts = {item.lower() for item in settings.ingest_url_blocked_hosts}
    host_is_allowed = normalised_host in allowed_hosts if allowed_hosts else False

    if allowed_hosts and not host_is_allowed:
        raise UnsupportedSourceError("URL target is not allowed for ingestion")

    if normalised_host in blocked_hosts and not host_is_allowed:
        raise UnsupportedSourceError("URL target is not allowed for ingestion")

    try:
        ip = ip_address(normalised_host)
    except ValueError:
        ip = None

    if ip is not None and not host_is_allowed:
        if settings.ingest_url_block_private_networks and (
            ip.is_loopback or ip.is_private or ip.is_reserved or ip.is_link_local
        ):
            raise UnsupportedSourceError("URL target is not allowed for ingestion")

        for network in _parse_blocked_networks(settings.ingest_url_blocked_ip_networks):
            if ip in network:
                raise UnsupportedSourceError("URL target is not allowed for ingestion")


class _LoopDetectingRedirectHandler(HTTPRedirectHandler):
    """HTTP redirect handler that guards against loops and deep chains."""

    def __init__(self, max_redirects: int) -> None:
        super().__init__()
        self.max_redirects = max_redirects
        self.redirect_count = 0
        self.visited: set[str] = set()

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        location = headers.get("Location") if headers else None
        if not location:
            raise UnsupportedSourceError("Redirect response missing Location header")

        resolved = urljoin(getattr(req, "full_url", req.get_full_url()), location)
        if resolved in self.visited:
            raise UnsupportedSourceError("URL redirect loop detected")

        self.redirect_count += 1
        if self.redirect_count > self.max_redirects:
            raise UnsupportedSourceError("URL exceeded maximum redirect depth")

        self.visited.add(resolved)
        redirected = super().redirect_request(req, fp, code, msg, headers, resolved)

        if redirected is not None:
            timeout = getattr(req, "timeout", None)
            if timeout is not None:
                setattr(redirected, "timeout", timeout)

        return redirected


def fetch_web_document(settings, url: str) -> tuple[str, dict[str, str | None]]:
    ensure_url_allowed(settings, url)

    timeout = getattr(settings, "ingest_web_timeout_seconds", 10.0)
    max_bytes = getattr(settings, "ingest_web_max_bytes", None)
    max_redirects = getattr(settings, "ingest_web_max_redirects", 5)

    redirect_handler = _LoopDetectingRedirectHandler(max_redirects)
    redirect_handler.visited.add(url)

    opener = build_opener(redirect_handler)
    opener.addheaders = [("User-Agent", settings.user_agent)]

    request = Request(url, headers={"User-Agent": settings.user_agent})

    try:
        response = opener.open(request, timeout=timeout)
    except UnsupportedSourceError:
        raise
    except socket.timeout as exc:  # pragma: no cover - handled in read loop tests
        raise UnsupportedSourceError(
            f"Fetching URL timed out after {timeout} seconds"
        ) from exc
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise UnsupportedSourceError(f"Unable to fetch URL: {url}") from exc

    raw = bytearray()
    final_url = url

    try:
        final_url = response.geturl()
        ensure_url_allowed(settings, final_url)

        while True:
            chunk = response.read(_WEB_FETCH_CHUNK_SIZE)
            if not chunk:
                break
            raw.extend(chunk)
            if max_bytes is not None and len(raw) > max_bytes:
                raise UnsupportedSourceError(
                    "Fetched content exceeded maximum allowed size of "
                    f"{max_bytes} bytes"
                )
    except socket.timeout as exc:
        raise UnsupportedSourceError(
            f"Fetching URL timed out after {timeout} seconds"
        ) from exc
    finally:
        response.close()

    encoding = response.headers.get_content_charset() or "utf-8"
    try:
        html = raw.decode(encoding, errors="replace")
    except LookupError:
        html = raw.decode("utf-8", errors="replace")

    metadata = parse_html_metadata(html)
    metadata.setdefault("canonical_url", final_url)
    metadata.setdefault("title", None)
    metadata["source_url"] = metadata.get("canonical_url") or final_url
    metadata["final_url"] = final_url
    return html, metadata


def _resolve_fixtures_dir(settings) -> Path | None:
    base = getattr(settings, "fixtures_dir", None)
    if base:
        candidate = Path(base)
        if candidate.exists():
            return candidate

    candidates: list[Path] = []
    configured = getattr(settings, "ingest_fixture_dirs", None)
    if configured:
        for item in configured:
            candidate = Path(item)
            if candidate.exists():
                candidates.append(candidate)

    fixtures_env = getattr(settings, "fixtures_dir_env", None)
    if fixtures_env:
        env_path = Path(fixtures_env)
        if env_path.exists():
            candidates.append(env_path)

    candidates.append(Path(__file__).resolve().parents[5] / "fixtures")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_youtube_transcript(settings, video_id: str):
    from ..parsers import TranscriptSegment as ParsedTranscriptSegment, load_transcript

    fixtures_dir = _resolve_fixtures_dir(settings)
    transcript_path: Path | None = None
    if fixtures_dir:
        base = fixtures_dir / "youtube"
        for suffix in (".vtt", ".webvtt", ".json", ".srt"):
            candidate = base / f"{video_id}{suffix}"
            if candidate.exists():
                transcript_path = candidate
                break

    segments: list[ParsedTranscriptSegment] = []
    if transcript_path:
        segments = load_transcript(transcript_path)
    else:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
        except ImportError as exc:  # pragma: no cover - defensive fallback
            raise UnsupportedSourceError(
                "youtube-transcript-api not installed and no transcript fixture found"
            ) from exc

        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as exc:  # pragma: no cover - network failure fallback
            raise UnsupportedSourceError(
                f"Unable to fetch transcript for video {video_id}"
            ) from exc

        for item in transcript:
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            start = float(item.get("start", 0.0))
            duration = float(item.get("duration", 0.0))
            segments.append(
                ParsedTranscriptSegment(
                    text=text,
                    start=start,
                    end=start + duration,
                )
            )

    if not segments:
        raise UnsupportedSourceError(f"No transcript segments found for {video_id}")
    return segments, transcript_path


def load_youtube_metadata(settings, video_id: str) -> dict[str, Any]:
    fixtures_dir = _resolve_fixtures_dir(settings)
    if not fixtures_dir:
        return {}
    meta_path = fixtures_dir / "youtube" / f"{video_id}.meta.json"
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def extract_youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "youtube" in host:
        if parsed.path == "/watch":
            qs = parse_qs(parsed.query)
            vid = qs.get("v", [None])[0]
            if vid:
                return vid
        elif parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[1].split("/")[0]
        elif parsed.path.startswith("/") and len(parsed.path.strip("/")) > 0:
            return parsed.path.strip("/")
    if "youtu.be" in host:
        return parsed.path.strip("/")
    raise UnsupportedSourceError(f"Unsupported URL for ingestion: {url}")


def is_youtube_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "youtube" in host or "youtu.be" in host


__all__ = [
    "ensure_url_allowed",
    "extract_youtube_video_id",
    "fetch_web_document",
    "is_youtube_url",
    "load_youtube_metadata",
    "load_youtube_transcript",
]
