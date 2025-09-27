"""HTTP middleware to generate structured debug reports on failures."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from .reporting import (
    SAFE_ENV_PREFIXES,
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
        include_client_errors: bool = False,
        response_on_error: bool = False,
        extra_context: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(app)
        self.logger = logger or logging.getLogger("theo.api.errors")
        self.env_prefixes = tuple(env_prefixes) if env_prefixes is not None else SAFE_ENV_PREFIXES
        self.body_max_bytes = body_max_bytes
        self.include_client_errors = include_client_errors
        self.response_on_error = response_on_error
        self.base_context = dict(extra_context or {})

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):  # type: ignore[override]
        body = await request.body()
        # Rehydrate the request stream so downstream handlers can read the body.
        request._body = body  # type: ignore[attr-defined]

        try:
            response = await call_next(request)
        except Exception as exc:
            report = self._build_report(request, body=body, exc=exc)
            emit_debug_report(report, logger=self.logger)
            if self.response_on_error:
                payload = {"detail": "Internal Server Error", "debug_report_id": report.id}
                return JSONResponse(status_code=500, content=payload)
            raise

        if self.include_client_errors and response.status_code >= 400:
            report = self._build_report(request, body=body, exc=None)
            report.context = {**report.context, "response_status": response.status_code}
            emit_debug_report(report, logger=self.logger)
        elif response.status_code >= 500:
            report = self._build_report(request, body=body, exc=None)
            report.context = {**report.context, "response_status": response.status_code}
            emit_debug_report(report, logger=self.logger)

        return response

    def _build_report(self, request: Request, *, body: bytes | None, exc: Exception | None) -> DebugReport:
        context = {**self.base_context}
        if hasattr(request.state, "workflow"):
            context.setdefault("workflow", getattr(request.state, "workflow"))
        if hasattr(request.state, "request_id"):
            context.setdefault("request_id", getattr(request.state, "request_id"))
        return build_debug_report(
            request,
            exc=exc,
            body=body,
            context=context,
            env_prefixes=self.env_prefixes,
            body_max_bytes=self.body_max_bytes,
        )


__all__ = ["ErrorReportingMiddleware"]
