"""Input validation and sanitization for MCP requests."""

from __future__ import annotations

import re
from typing import Any

from fastapi import status

from .errors import ValidationError as MCPValidationError

# Security constraints for MCP inputs
MAX_QUERY_LENGTH = 2000
MAX_BODY_LENGTH = 50000
MAX_FILTER_VALUES = 20
MAX_ARRAY_LENGTH = 100
MAX_HEADER_LENGTH = 256

# Patterns for header validation
VALID_USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.@]{1,256}$")
VALID_TENANT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")
VALID_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")

# Dangerous patterns that should never appear in user input
INJECTION_PATTERNS = [
    (re.compile(r"<\s*script[^>]*>", re.IGNORECASE), "script tag"),
    (re.compile(r"javascript\s*:", re.IGNORECASE), "javascript protocol"),
    (re.compile(r"on\w+\s*=", re.IGNORECASE), "event handler attribute"),
    (re.compile(r"<\s*iframe[^>]*>", re.IGNORECASE), "iframe tag"),
    (re.compile(r"<\s*object[^>]*>", re.IGNORECASE), "object tag"),
    (re.compile(r"<\s*embed[^>]*>", re.IGNORECASE), "embed tag"),
    (re.compile(r"\beval\s*\(", re.IGNORECASE), "eval function"),
    (re.compile(r"\.\.[\\/]", re.IGNORECASE), "path traversal"),
]


class ValidationError(MCPValidationError):
    """Raised when request validation fails."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message=message, field=field)


def validate_header(
    value: str | None,
    header_name: str,
    pattern: re.Pattern[str] | None = None,
    required: bool = True,
) -> str | None:
    """Validate and sanitize a header value."""
    if value is None:
        if required:
            raise ValidationError(f"Header {header_name} is required", header_name)
        return None

    if not isinstance(value, str):
        raise ValidationError(f"Header {header_name} must be a string", header_name)

    if len(value) > MAX_HEADER_LENGTH:
        raise ValidationError(
            f"Header {header_name} exceeds maximum length of {MAX_HEADER_LENGTH}",
            header_name,
        )

    value = value.strip()
    if not value:
        if required:
            raise ValidationError(f"Header {header_name} cannot be empty", header_name)
        return None

    if pattern and not pattern.match(value):
        raise ValidationError(
            f"Header {header_name} contains invalid characters",
            header_name,
        )

    return value


def validate_end_user_id(value: str) -> str:
    """Validate end_user_id header."""
    validated = validate_header(value, "X-End-User-Id", VALID_USER_ID_PATTERN, required=True)
    if not validated:
        raise ValidationError("end_user_id is required", "X-End-User-Id")
    return validated


def validate_tenant_id(value: str | None) -> str | None:
    """Validate tenant_id header."""
    if value is None:
        return None
    return validate_header(value, "X-Tenant-Id", VALID_TENANT_ID_PATTERN, required=False)


def validate_idempotency_key(value: str | None) -> str | None:
    """Validate idempotency_key header."""
    if value is None:
        return None
    return validate_header(
        value, "X-Idempotency-Key", VALID_IDEMPOTENCY_KEY_PATTERN, required=False
    )


def check_injection_patterns(text: str, field_name: str) -> None:
    """Scan text for common injection attack patterns."""
    for pattern, description in INJECTION_PATTERNS:
        if pattern.search(text):
            raise ValidationError(
                message=f"Detected potential security risk: {description}",
                field=field_name,
            )


def validate_string_length(
    value: str | None,
    field_name: str,
    max_length: int,
    min_length: int = 0,
) -> None:
    """Validate string length constraints."""
    if value is None:
        return
    if len(value) < min_length:
        raise ValidationError(
            f"Must be at least {min_length} characters",
            field_name,
        )
    if len(value) > max_length:
        raise ValidationError(
            f"Exceeds maximum length of {max_length} characters",
            field_name,
        )


def validate_array_length(
    value: list[Any] | None,
    field_name: str,
    max_length: int = MAX_ARRAY_LENGTH,
) -> None:
    """Validate array length constraints."""
    if value is None:
        return
    if not isinstance(value, list):
        raise ValidationError("Must be an array", field_name)
    if len(value) > max_length:
        raise ValidationError(
            f"Exceeds maximum array length of {max_length}",
            field_name,
        )


def validate_query(query: str | None) -> None:
    """Validate search query input."""
    if query is None:
        return
    validate_string_length(query, "query", MAX_QUERY_LENGTH)
    check_injection_patterns(query, "query")


def validate_body_text(body: str | None) -> None:
    """Validate body text input."""
    if body is None:
        return
    validate_string_length(body, "body", MAX_BODY_LENGTH)
    check_injection_patterns(body, "body")


def validate_filters(filters: dict[str, Any] | None) -> None:
    """Validate filter dictionary."""
    if filters is None:
        return
    if not isinstance(filters, dict):
        raise ValidationError("filters must be a dictionary", "filters")
    if len(filters) > MAX_FILTER_VALUES:
        raise ValidationError(
            f"filters exceeds maximum of {MAX_FILTER_VALUES} entries",
            "filters",
        )
    for key, value in filters.items():
        if isinstance(value, str):
            validate_string_length(value, f"filters.{key}", MAX_QUERY_LENGTH)
            check_injection_patterns(value, f"filters.{key}")


def validate_osis_reference(osis: str | None) -> None:
    """Validate OSIS scripture reference format."""
    if osis is None:
        return
    if not isinstance(osis, str):
        raise ValidationError("OSIS reference must be a string", "osis")
    # Basic OSIS format validation
    if len(osis) > 100:
        raise ValidationError("OSIS reference too long", "osis")
    if not re.match(r"^[A-Za-z0-9\.]+(\.[0-9]+)*$", osis):
        raise ValidationError(
            "OSIS reference format invalid (expected Book.Chapter.Verse)",
            "osis",
        )


__all__ = [
    "ValidationError",
    "validate_header",
    "validate_end_user_id",
    "validate_tenant_id",
    "validate_idempotency_key",
    "validate_query",
    "validate_body_text",
    "validate_filters",
    "validate_osis_reference",
    "validate_array_length",
    "check_injection_patterns",
    "MAX_QUERY_LENGTH",
    "MAX_BODY_LENGTH",
]
