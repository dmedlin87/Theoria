"""Middleware utilities for the API bootstrap process."""

from __future__ import annotations

from typing import Iterable

from fastapi import Depends, FastAPI, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from ..debug import ErrorReportingMiddleware
from ..errors import TheoError
from ..ingest.exceptions import UnsupportedSourceError
from ..adapters.security import require_principal
from ..tracing import TRACE_ID_HEADER_NAME, get_current_trace_headers

__all__ = [
    "configure_cors",
    "install_error_reporting",
    "register_trace_handlers",
    "get_security_dependencies",
]


def configure_cors(app: FastAPI, *, allow_origins: Iterable[str] | None) -> None:
    """Install the CORS middleware if any origins are configured."""

    origins = list(allow_origins or ())
    if not origins:
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "X-Requested-With",
        ],
    )


def install_error_reporting(app: FastAPI) -> None:
    """Attach error reporting middleware to the application."""

    app.add_middleware(
        ErrorReportingMiddleware,
        extra_context={"service": "api"},
    )


def _attach_trace_headers(response: Response, trace_headers: dict[str, str] | None = None) -> Response:
    headers = trace_headers or get_current_trace_headers()
    for key, value in headers.items():
        if key not in response.headers:
            response.headers[key] = value
    return response


def register_trace_handlers(app: FastAPI) -> None:
    """Install middleware and exception handlers that propagate trace headers."""

    @app.middleware("http")
    async def add_trace_headers(request: Request, call_next: RequestResponseEndpoint):
        response = await call_next(request)
        return _attach_trace_headers(response)

    @app.exception_handler(HTTPException)
    async def http_exception_with_trace(request: Request, exc: HTTPException) -> Response:  # type: ignore[override]
        response = await http_exception_handler(request, exc)
        return _attach_trace_headers(response)

    @app.exception_handler(TheoError)
    async def theo_error_handler(request: Request, exc: TheoError) -> Response:
        trace_headers = get_current_trace_headers()
        trace_id = trace_headers.get(TRACE_ID_HEADER_NAME) or request.headers.get(
            TRACE_ID_HEADER_NAME
        )
        if trace_id and TRACE_ID_HEADER_NAME not in trace_headers:
            trace_headers[TRACE_ID_HEADER_NAME] = trace_id
        request.state._last_domain_error = exc  # type: ignore[attr-defined]
        response = exc.to_response(trace_id=trace_id)
        return _attach_trace_headers(response, trace_headers)

    @app.exception_handler(UnsupportedSourceError)
    async def unsupported_source_error_with_trace(
        request: Request, exc: UnsupportedSourceError
    ) -> Response:
        request.state._last_domain_error = exc  # type: ignore[attr-defined]
        response = JSONResponse({"detail": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
        return _attach_trace_headers(response)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_with_trace(
        request: Request, exc: RequestValidationError
    ) -> Response:  # type: ignore[override]
        response = await request_validation_exception_handler(request, exc)
        return _attach_trace_headers(response)

    @app.exception_handler(Exception)
    async def unhandled_exception_with_trace(
        request: Request, exc: Exception
    ) -> Response:  # type: ignore[override]
        del exc
        trace_headers = get_current_trace_headers()
        body: dict[str, str] = {"detail": "Internal Server Error"}
        trace_id = trace_headers.get(TRACE_ID_HEADER_NAME)
        if trace_id:
            body["trace_id"] = trace_id
        response = JSONResponse(body, status_code=500)
        return _attach_trace_headers(response, trace_headers)


def get_security_dependencies() -> list[Depends]:
    """Return the dependencies required for secured routes."""

    return [Depends(require_principal)]
