"""Standardized error handling middleware.

Maps domain errors to consistent HTTP responses with proper status codes
and structured error payloads.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from theo.domain.errors import (
    AuthorizationError,
    ConflictError,
    DomainError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

from .tracing import TRACE_ID_HEADER_NAME, get_current_trace_headers

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)


# Map domain errors to HTTP status codes
ERROR_STATUS_MAP = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    AuthorizationError: status.HTTP_403_FORBIDDEN,
    ConflictError: status.HTTP_409_CONFLICT,
    RateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,
    ExternalServiceError: status.HTTP_502_BAD_GATEWAY,
    DomainError: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def _build_error_response(
    exc: DomainError,
    status_code: int,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Build standardized error response payload."""
    response: dict[str, Any] = {
        "error": {
            "type": exc.__class__.__name__,
            "code": exc.code,
            "message": exc.message,
        }
    }

    if exc.details:
        response["error"]["details"] = exc.details

    if isinstance(exc, NotFoundError):
        response["error"]["resource_type"] = exc.resource_type
        response["error"]["resource_id"] = exc.resource_id

    if isinstance(exc, ValidationError) and exc.field:
        response["error"]["field"] = exc.field

    if isinstance(exc, RateLimitError) and exc.retry_after:
        response["error"]["retry_after"] = exc.retry_after

    if isinstance(exc, ExternalServiceError):
        response["error"]["service"] = exc.service

    if trace_id:
        response["trace_id"] = trace_id

    return response


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Handle domain-level errors with consistent response format."""
    # Determine HTTP status code
    status_code = ERROR_STATUS_MAP.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Get trace ID for observability
    trace_headers = get_current_trace_headers()
    trace_id = trace_headers.get(TRACE_ID_HEADER_NAME) or request.headers.get(
        TRACE_ID_HEADER_NAME
    )

    # Build response
    response_body = _build_error_response(exc, status_code, trace_id)

    # Log error for monitoring
    if status_code >= 500:
        logger.error(
            "Domain error in %s %s: %s",
            request.method,
            request.url.path,
            exc.message,
            exc_info=exc,
            extra={"trace_id": trace_id, "error_code": exc.code},
        )
    else:
        logger.warning(
            "Client error in %s %s: %s",
            request.method,
            request.url.path,
            exc.message,
            extra={"trace_id": trace_id, "error_code": exc.code},
        )

    # Attach trace headers
    response = JSONResponse(
        status_code=status_code,
        content=response_body,
    )
    for key, value in trace_headers.items():
        response.headers[key] = value

    # Add Retry-After header for rate limiting
    if isinstance(exc, RateLimitError) and exc.retry_after:
        response.headers["Retry-After"] = str(exc.retry_after)

    return response


def install_error_handlers(app: FastAPI) -> None:
    """Install standardized error handlers on the FastAPI application."""
    app.add_exception_handler(DomainError, domain_error_handler)

    # Ensure all domain error subclasses are handled
    for error_class in [
        NotFoundError,
        ValidationError,
        AuthorizationError,
        ConflictError,
        RateLimitError,
        ExternalServiceError,
    ]:
        app.add_exception_handler(error_class, domain_error_handler)

    logger.info("Installed standardized domain error handlers")


__all__ = [
    "domain_error_handler",
    "install_error_handlers",
]
