"""Unit tests for :mod:`theo.domain.errors`."""
from __future__ import annotations

import pytest

from theo.domain import errors


def test_domain_error_defaults():
    err = errors.DomainError("something went wrong")

    assert err.message == "something went wrong"
    assert err.code == "DomainError"
    assert err.details == {}


def test_domain_error_allows_custom_code_and_details():
    err = errors.DomainError("failure", code="E_CUSTOM", details={"hint": "check input"})

    assert err.code == "E_CUSTOM"
    assert err.details == {"hint": "check input"}


@pytest.mark.parametrize(
    "resource_type,resource_id,expected_message",
    [
        ("Widget", 5, "Widget with ID '5' not found"),
        ("Document", "abc", "Document with ID 'abc' not found"),
    ],
)
def test_not_found_error_formats_message(resource_type: str, resource_id: str | int, expected_message: str):
    err = errors.NotFoundError(resource_type, resource_id)

    assert err.message == expected_message
    assert err.resource_type == resource_type
    assert err.resource_id == str(resource_id)


def test_validation_error_preserves_field_information():
    err = errors.ValidationError("Invalid title", field="title")

    assert err.message == "Invalid title"
    assert err.field == "title"


@pytest.mark.parametrize(
    "exception_type",
    [errors.AuthorizationError, errors.ConflictError],
)
def test_simple_error_types_inherit_domain_error(exception_type: type[Exception]):
    err = exception_type("message")

    assert isinstance(err, errors.DomainError)
    assert err.code == exception_type.__name__


def test_rate_limit_error_tracks_retry_after():
    err = errors.RateLimitError("Too many requests", retry_after=30)

    assert err.retry_after == 30
    assert err.message == "Too many requests"


def test_external_service_error_prefixes_service_name():
    err = errors.ExternalServiceError("search", "timeout")

    assert err.service == "search"
    assert err.message == "search: timeout"


def test_module_exports_are_declared():
    exported = set(errors.__all__)
    expected = {
        "DomainError",
        "NotFoundError",
        "ValidationError",
        "AuthorizationError",
        "ConflictError",
        "RateLimitError",
        "ExternalServiceError",
    }

    assert expected <= exported
