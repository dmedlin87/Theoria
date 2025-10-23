"""Domain-level error hierarchy.

These exceptions represent business rule violations and domain-specific
error conditions. They are mapped to HTTP status codes at the API boundary.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors."""

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}


class NotFoundError(DomainError):
    """Resource not found in the system."""

    def __init__(self, resource_type: str, resource_id: str | int, **kwargs):
        super().__init__(
            f"{resource_type} with ID '{resource_id}' not found",
            **kwargs,
        )
        self.resource_type = resource_type
        self.resource_id = str(resource_id)


class ValidationError(DomainError):
    """Input validation failed."""

    def __init__(self, message: str, *, field: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.field = field


class AuthorizationError(DomainError):
    """User lacks permission for the requested operation."""

    pass


class ConflictError(DomainError):
    """Operation conflicts with current system state."""

    pass


class RateLimitError(DomainError):
    """Rate limit exceeded for the operation."""

    def __init__(self, message: str, *, retry_after: int | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ExternalServiceError(DomainError):
    """External service call failed."""

    def __init__(self, service: str, message: str, **kwargs):
        super().__init__(f"{service}: {message}", **kwargs)
        self.service = service


__all__ = [
    "DomainError",
    "NotFoundError",
    "ValidationError",
    "AuthorizationError",
    "ConflictError",
    "RateLimitError",
    "ExternalServiceError",
]
