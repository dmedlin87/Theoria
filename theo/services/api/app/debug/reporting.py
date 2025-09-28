"""Utilities for building structured error/debug reports."""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from fastapi import Request

SAFE_HEADER_PREFIXES = ("x-", "cf-", "forwarded")
SAFE_ENV_PREFIXES = ("THEO_", "APP_", "FEATURE_")
LOGGER = logging.getLogger("theo.api.errors")


@dataclass(slots=True)
class BodyCapture:
    """Representation of a captured request body preview."""

    preview: bytes
    total_bytes: int | None = None
    complete: bool = True


@dataclass(slots=True)
class DebugReport:
    """Container for structured error reports."""

    id: str
    created_at: datetime
    request: Mapping[str, Any]
    runtime: Mapping[str, Any]
    environment: Mapping[str, Any]
    error: Mapping[str, Any] | None
    context: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "request": dict(self.request),
            "runtime": dict(self.runtime),
            "environment": dict(self.environment),
            "error": dict(self.error) if self.error is not None else None,
            "context": dict(self.context),
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True)


def _filter_headers(headers: Mapping[str, str]) -> dict[str, str]:
    filtered: dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered in {"authorization", "cookie"}:
            continue
        if lowered.startswith(SAFE_HEADER_PREFIXES):
            filtered[lowered] = value
    return filtered


def _collect_request_context(
    request: Request, *, body: bytes | BodyCapture | None, body_max_bytes: int
) -> dict[str, Any]:
    client_host, client_port = None, None
    if request.client is not None:
        client_host, client_port = request.client

    context: dict[str, Any] = {
        "method": request.method,
        "url": str(request.url),
        "path": request.url.path,
        "query": request.url.query,
        "client": {"host": client_host, "port": client_port},
        "headers": _filter_headers(request.headers),
    }

    capture: BodyCapture | None
    if isinstance(body, BodyCapture):
        capture = body
    elif isinstance(body, (bytes, bytearray)):
        capture = BodyCapture(preview=bytes(body), total_bytes=len(body), complete=True)
    else:
        capture = None

    if capture:
        preview = capture.preview[:body_max_bytes]
        truncated_preview = len(capture.preview) > body_max_bytes
        total_bytes = capture.total_bytes if capture.total_bytes is not None else len(capture.preview)
        truncated = (
            truncated_preview
            or not capture.complete
            or (capture.total_bytes is not None and capture.total_bytes > len(capture.preview))
        )
        try:
            body_text = preview.decode("utf-8", errors="replace")
        except Exception:
            body_text = preview.hex()
        context["body"] = {
            "truncated": truncated,
            "preview": body_text,
            "bytes": total_bytes,
        }
    return context


def _collect_runtime_context() -> dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "executable": sys.executable,
        "platform": platform.platform(),
        "pid": os.getpid(),
    }


def _collect_environment(prefixes: Iterable[str]) -> dict[str, str]:
    safe_env: dict[str, str] = {}
    for key, value in os.environ.items():
        if any(key.startswith(prefix) for prefix in prefixes):
            safe_env[key] = value
    return safe_env


def _collect_error_context(exc: Exception | None) -> dict[str, Any] | None:
    if exc is None:
        return None
    tb = traceback.TracebackException.from_exception(exc)
    return {
        "type": tb.exc_type.__name__ if tb.exc_type else exc.__class__.__name__,
        "message": str(exc),
        "stacktrace": list(tb.format()),
    }


def build_debug_report(
    request: Request,
    *,
    exc: Exception | None,
    body: bytes | BodyCapture | None,
    context: Mapping[str, Any] | None = None,
    env_prefixes: Iterable[str] = SAFE_ENV_PREFIXES,
    body_max_bytes: int = 2048,
) -> DebugReport:
    """Generate a structured debug report for an API failure."""

    report_id = uuid.uuid4().hex
    request_context = _collect_request_context(request, body=body, body_max_bytes=body_max_bytes)
    runtime_context = _collect_runtime_context()
    environment_context = _collect_environment(env_prefixes)
    error_context = _collect_error_context(exc)

    report_context = dict(context or {})
    report_context.setdefault("request_id", report_id)

    return DebugReport(
        id=report_id,
        created_at=datetime.now(timezone.utc),
        request=request_context,
        runtime=runtime_context,
        environment=environment_context,
        error=error_context,
        context=report_context,
    )


def emit_debug_report(report: DebugReport, *, logger: logging.Logger | None = None) -> None:
    """Log the structured report for downstream processing."""

    target_logger = logger or LOGGER
    target_logger.error(
        "api.debug_report",
        extra={"debug_report": report.as_dict()},
    )


__all__ = [
    "BodyCapture",
    "DebugReport",
    "build_debug_report",
    "emit_debug_report",
    "SAFE_ENV_PREFIXES",
    "SAFE_HEADER_PREFIXES",
]
