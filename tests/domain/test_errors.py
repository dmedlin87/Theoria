"""Tests for domain error hierarchy behaviours."""

import pytest

from theo.domain.errors import (
    AuthorizationError,
    ConflictError,
    DomainError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


def test_error_hierarchy_inheritance():
    assert issubclass(AuthorizationError, DomainError)
    assert issubclass(ConflictError, DomainError)
    assert issubclass(RateLimitError, DomainError)
    assert issubclass(ValidationError, DomainError)
    assert issubclass(NotFoundError, DomainError)


@pytest.mark.parametrize(
    "error_cls, kwargs, expected_code",
    [
        (DomainError, {"message": "oops"}, "DomainError"),
        (AuthorizationError, {"message": "denied"}, "AuthorizationError"),
        (ConflictError, {"message": "boom"}, "ConflictError"),
    ],
)
def test_domain_error_defaults(error_cls, kwargs, expected_code):
    error = error_cls(**kwargs)

    assert error.message == kwargs["message"]
    assert error.code == expected_code
    assert error.details == {}

    # mutating the returned details reflects on the stored mapping
    details = error.details
    details["changed"] = True
    assert error.details == {"changed": True}


def test_domain_error_allows_custom_code_and_details():
    details = {"foo": "bar"}
    error = DomainError("broken", code="custom", details=details)

    assert error.code == "custom"
    assert error.details == details
    assert error.details is details


def test_domain_error_default_details_are_isolated():
    first = DomainError("first")
    second = DomainError("second")

    first.details["key"] = "value"

    assert first.details == {"key": "value"}
    assert second.details == {}


def test_not_found_error_sets_message_and_metadata():
    error = NotFoundError("Document", 42)

    assert error.message == "Document with ID '42' not found"
    assert error.resource_type == "Document"
    assert error.resource_id == "42"
    assert error.code == "NotFoundError"


@pytest.mark.parametrize(
    "field, expected",
    [(None, None), ("title", "title")],
)
def test_validation_error_tracks_field(field, expected):
    error = ValidationError("invalid", field=field)

    assert error.field == expected


@pytest.mark.parametrize("retry_after", [None, 30])
def test_rate_limit_error_preserves_retry_after(retry_after):
    error = RateLimitError("too many", retry_after=retry_after)

    assert error.retry_after == retry_after
    assert error.code == "RateLimitError"


def test_external_service_error_prefixes_service_name():
    error = ExternalServiceError("llm", "timeout", code="LLMTimeout")

    assert str(error) == "llm: timeout"
    assert error.message == "llm: timeout"
    assert error.service == "llm"
    assert error.code == "LLMTimeout"
