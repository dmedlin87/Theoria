"""Structured error handling for MCP server."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorCode(str, Enum):
    """Standard error codes for MCP operations."""

    # Client errors (4xx)
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    RESOURCE_NOT_FOUND = "resource_not_found"
    CONFLICT = "conflict"
    PAYLOAD_TOO_LARGE = "payload_too_large"

    # Server errors (5xx)
    INTERNAL_ERROR = "internal_error"
    DATABASE_ERROR = "database_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    TIMEOUT_ERROR = "timeout_error"


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: ErrorCode
    message: str
    field: str | None = None
    details: Dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standardized error response format."""

    error: ErrorDetail
    request_id: str | None = None
    timestamp: str | None = None


class MCPError(HTTPException):
    """Base exception for MCP operations with structured error details."""

    def __init__(
        self,
        status_code: int,
        error_code: ErrorCode,
        message: str,
        field: str | None = None,
        details: Dict[str, Any] | None = None,
        headers: Dict[str, str] | None = None,
    ) -> None:
        self.error_code = error_code
        self.field = field
        self.error_details = details
        super().__init__(status_code=status_code, detail=message, headers=headers)


class ValidationError(MCPError):
    """Validation error with field-level details."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        details: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code=ErrorCode.VALIDATION_ERROR,
            message=message,
            field=field,
            details=details,
        )


class AuthenticationError(MCPError):
    """Authentication failure."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=ErrorCode.AUTHENTICATION_ERROR,
            message=message,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(MCPError):
    """Authorization/permission error."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=ErrorCode.AUTHORIZATION_ERROR,
            message=message,
        )


class RateLimitError(MCPError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
    ) -> None:
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            headers=headers,
        )


async def mcp_error_handler(request: Request, exc: MCPError) -> JSONResponse:
    """Convert MCPError exceptions to standardized JSON responses."""
    from datetime import datetime, timezone

    error_detail = ErrorDetail(
        code=exc.error_code,
        message=exc.detail,
        field=exc.field,
        details=exc.error_details,
    )

    error_response = ErrorResponse(
        error=error_detail,
        request_id=request.headers.get("X-Request-ID"),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(exclude_none=True),
        headers=exc.headers,
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with structured error format."""
    from datetime import datetime, timezone
    import logging

    logger = logging.getLogger(__name__)
    logger.exception("Unhandled exception in MCP server", exc_info=exc)

    error_detail = ErrorDetail(
        code=ErrorCode.INTERNAL_ERROR,
        message="An unexpected error occurred",
    )

    error_response = ErrorResponse(
        error=error_detail,
        request_id=request.headers.get("X-Request-ID"),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(exclude_none=True),
    )


__all__ = [
    "ErrorCode",
    "ErrorDetail",
    "ErrorResponse",
    "MCPError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    "mcp_error_handler",
    "generic_error_handler",
]
