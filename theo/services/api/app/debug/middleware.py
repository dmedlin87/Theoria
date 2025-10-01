"""HTTP middleware to generate structured debug reports on failures."""

from __future__ import annotations

import logging
from collections import deque
from typing import Any, Deque, Iterable, Mapping

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp, Message

from .reporting import (
    SAFE_ENV_PREFIXES,
    BodyCapture,
    DebugReport,
    build_debug_report,
    emit_debug_report,
)


class ErrorReportingMiddleware(BaseHTTPMiddleware):
    """Capture request/exception context and emit debug reports."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        logger: logging.Logger | None = None,
        env_prefixes: Iterable[str] | None = None,
        body_max_bytes: int = 2048,
        stream_preview_limit: int = 64 * 1024,
        include_client_errors: bool = False,
        response_on_error: bool = False,
        extra_context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(app)
        self.logger = logger or logging.getLogger("theo.api.errors")
        self.env_prefixes = tuple(env_prefixes) if env_prefixes is not None else SAFE_ENV_PREFIXES
        self.body_max_bytes = body_max_bytes
        self.stream_preview_limit = stream_preview_limit
        self.include_client_errors = include_client_errors
        self.response_on_error = response_on_error
        self.base_context = dict(extra_context or {})

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):  # type: ignore[override]
        body_capture = await self._capture_request_body(request)

        try:
            response = await call_next(request)
        except Exception as exc:
            report = self._build_report(request, body=body_capture, exc=exc)
            emit_debug_report(report, logger=self.logger)
            if self.response_on_error:
                payload = {"detail": "Internal Server Error", "debug_report_id": report.id}
                return JSONResponse(status_code=500, content=payload)
            raise

        if self.include_client_errors and response.status_code >= 400:
            report = self._build_report(request, body=body_capture, exc=None)
            report.context = {**report.context, "response_status": response.status_code}
            emit_debug_report(report, logger=self.logger)
        elif response.status_code >= 500:
            report = self._build_report(request, body=body_capture, exc=None)
            report.context = {**report.context, "response_status": response.status_code}
            emit_debug_report(report, logger=self.logger)

        return response

    async def _capture_request_body(self, request: Request) -> BodyCapture | None:
        """Capture a limited preview of the request body without exhausting the stream."""

        if request.method in {"GET", "DELETE", "HEAD", "OPTIONS"}:
            return None

        content_type = request.headers.get("content-type", "").lower()
        is_multipart = "multipart/form-data" in content_type

        raw_content_length = request.headers.get("content-length")
        content_length: int | None
        try:
            content_length = int(raw_content_length) if raw_content_length is not None else None
        except (TypeError, ValueError):
            content_length = None

        original_receive = request._receive  # type: ignore[attr-defined]
        cached_messages: Deque[Message] = deque()
        preview = bytearray()
        total = 0
        more_body_expected = False
        disconnected = False

        preview_limit = max(0, self.stream_preview_limit)

        try:
            while True:
                message = await original_receive()
                cached_messages.append(message)

                message_type = message.get("type")
                if message_type == "http.disconnect":
                    disconnected = True
                    break

                if message_type != "http.request":
                    continue

                chunk = message.get("body", b"") or b""
                if chunk:
                    total += len(chunk)
                    if preview_limit and len(preview) < preview_limit:
                        remaining = preview_limit - len(preview)
                        if remaining > 0:
                            preview.extend(chunk[:remaining])
                more_body_expected = bool(message.get("more_body", False))

                if not more_body_expected:
                    break
                if preview_limit and len(preview) >= preview_limit:
                    break
        except Exception:
            # Restore the original receive callable before propagating exceptions.
            request._receive = original_receive  # type: ignore[attr-defined]
            raise

        queue = deque(cached_messages)

        async def replay_receive() -> Message:
            if queue:
                return queue.popleft()
            return await original_receive()

        request._receive = replay_receive  # type: ignore[attr-defined]

        if not preview and total == 0:
            return None

        complete = not (disconnected or more_body_expected)
        if complete and content_length is not None:
            complete = total >= content_length

        total_bytes: int | None
        if content_length is not None:
            total_bytes = content_length
        elif complete:
            total_bytes = total
        else:
            total_bytes = None

        if is_multipart:
            complete = False

        return BodyCapture(preview=bytes(preview), total_bytes=total_bytes, complete=complete)

    def _build_report(
        self, request: Request, *, body: BodyCapture | bytes | None, exc: Exception | None
    ) -> DebugReport:
        context = {**self.base_context}
        if hasattr(request.state, "workflow"):
            context.setdefault("workflow", request.state.workflow)  # type: ignore[attr-defined]
        if hasattr(request.state, "request_id"):
            context.setdefault("request_id", request.state.request_id)  # type: ignore[attr-defined]
        return build_debug_report(
            request,
            exc=exc,
            body=body,
            context=context,
            env_prefixes=self.env_prefixes,
            body_max_bytes=self.body_max_bytes,
        )


__all__ = ["ErrorReportingMiddleware"]
