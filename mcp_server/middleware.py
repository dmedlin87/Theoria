"""Middleware components for MCP server."""

from __future__ import annotations

import time
from typing import Callable
from uuid import uuid4

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy
        csp_directives = [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self'",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add or propagate request IDs for distributed tracing."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        # Use existing request ID or generate new one
        request_id = request.headers.get("X-Request-ID") or str(uuid4())

        # Store in request state for access by handlers
        request.state.request_id = request_id

        response = await call_next(request)

        # Include request ID in response headers
        response.headers["X-Request-ID"] = request_id

        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Track request timing for performance monitoring."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        start_time = time.perf_counter()

        response = await call_next(request)

        # Calculate request duration
        duration = time.perf_counter() - start_time
        duration_ms = int(duration * 1000)

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        # Store in request state for logging
        request.state.duration_ms = duration_ms

        return response


class RequestLimitMiddleware(BaseHTTPMiddleware):
    """Enforce request size limits to prevent DoS attacks."""

    def __init__(self, app: ASGIApp, max_body_size: int = 10 * 1024 * 1024) -> None:
        super().__init__(app)
        self.max_body_size = max_body_size
        # Use literal to avoid deprecation warning until starlette adds HTTP_413_CONTENT_TOO_LARGE
        self._payload_limit_status = 413

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        from fastapi.responses import JSONResponse

        # Check Content-Length header if present
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_body_size:
                    return JSONResponse(
                        status_code=self._payload_limit_status,
                        content={
                            "error": {
                                "code": "payload_too_large",
                                "message": f"Request body exceeds maximum size of {self.max_body_size} bytes",
                            }
                        },
                    )
            except ValueError:
                pass

        return await call_next(request)


class CORSHeaderMiddleware(BaseHTTPMiddleware):
    """Add CORS headers for cross-origin requests."""

    def __init__(
        self,
        app: ASGIApp,
        allow_origins: list[str] | None = None,
        allow_credentials: bool = True,
    ) -> None:
        super().__init__(app)
        self.allow_origins = allow_origins or ["*"]
        self.allow_credentials = allow_credentials

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response()
            self._add_cors_headers(request, response)
            return response

        response = await call_next(request)
        self._add_cors_headers(request, response)
        return response

    def _add_cors_headers(self, request: Request, response: Response) -> None:
        """Add CORS headers to response."""
        origin = request.headers.get("origin")

        if origin and (
            "*" in self.allow_origins or origin in self.allow_origins
        ):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization, X-Request-ID, "
                "X-End-User-Id, X-Tenant-Id, X-Idempotency-Key"
            )
            response.headers["Access-Control-Expose-Headers"] = (
                "X-Request-ID, X-Response-Time"
            )

            if self.allow_credentials:
                response.headers["Access-Control-Allow-Credentials"] = "true"


__all__ = [
    "SecurityHeadersMiddleware",
    "RequestIDMiddleware",
    "RequestTimingMiddleware",
    "RequestLimitMiddleware",
    "CORSHeaderMiddleware",
]
