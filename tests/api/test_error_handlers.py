"""Comprehensive tests for error handling middleware and handlers."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from theo.domain.errors import (
    AuthorizationError,
    ConflictError,
    DomainError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from theo.infrastructure.api.app.error_handlers import (
    ERROR_STATUS_MAP,
    _build_error_response,
    domain_error_handler,
)
from theo.infrastructure.api.app.tracing import TRACE_ID_HEADER_NAME


class TestErrorStatusMapping:
    """Test error type to HTTP status code mapping."""

    def test_not_found_error_maps_to_404(self) -> None:
        """Test NotFoundError maps to 404."""
        assert ERROR_STATUS_MAP[NotFoundError] == 404

    def test_validation_error_maps_to_422(self) -> None:
        """Test ValidationError maps to 422."""
        assert ERROR_STATUS_MAP[ValidationError] == 422

    def test_authorization_error_maps_to_403(self) -> None:
        """Test AuthorizationError maps to 403."""
        assert ERROR_STATUS_MAP[AuthorizationError] == 403

    def test_conflict_error_maps_to_409(self) -> None:
        """Test ConflictError maps to 409."""
        assert ERROR_STATUS_MAP[ConflictError] == 409

    def test_rate_limit_error_maps_to_429(self) -> None:
        """Test RateLimitError maps to 429."""
        assert ERROR_STATUS_MAP[RateLimitError] == 429

    def test_external_service_error_maps_to_502(self) -> None:
        """Test ExternalServiceError maps to 502."""
        assert ERROR_STATUS_MAP[ExternalServiceError] == 502

    def test_generic_domain_error_maps_to_500(self) -> None:
        """Test generic DomainError maps to 500."""
        assert ERROR_STATUS_MAP[DomainError] == 500


class TestBuildErrorResponse:
    """Test error response payload building."""

    def test_build_basic_error_response(self) -> None:
        """Test building basic error response."""
        exc = DomainError(
            message="Something went wrong",
            code="GENERIC_ERROR",
        )

        response = _build_error_response(exc, 500)

        assert response["error"]["type"] == "DomainError"
        assert response["error"]["code"] == "GENERIC_ERROR"
        assert response["error"]["message"] == "Something went wrong"

    def test_build_error_response_with_details(self) -> None:
        """Test error response includes details when provided."""
        exc = DomainError(
            message="Validation failed",
            code="VALIDATION_ERROR",
            details={"field": "email", "reason": "invalid format"},
        )

        response = _build_error_response(exc, 422)

        assert response["error"]["details"] == {
            "field": "email",
            "reason": "invalid format",
        }

    def test_build_error_response_with_trace_id(self) -> None:
        """Test error response includes trace ID."""
        exc = DomainError(
            message="Error occurred",
            code="ERROR",
        )

        response = _build_error_response(exc, 500, trace_id="trace-123")

        assert response["trace_id"] == "trace-123"

    def test_build_not_found_error_includes_resource_info(self) -> None:
        """Test NotFoundError response includes resource type and ID."""
        exc = NotFoundError(
            resource_type="Document",
            resource_id="doc-123",
        )

        response = _build_error_response(exc, 404)

        assert response["error"]["resource_type"] == "Document"
        assert response["error"]["resource_id"] == "doc-123"

    def test_build_validation_error_includes_field(self) -> None:
        """Test ValidationError response includes field name."""
        exc = ValidationError(
            message="Invalid email",
            code="INVALID_EMAIL",
            field="email",
        )

        response = _build_error_response(exc, 422)

        assert response["error"]["field"] == "email"

    def test_build_rate_limit_error_includes_retry_after(self) -> None:
        """Test RateLimitError response includes retry_after."""
        exc = RateLimitError(
            message="Too many requests",
            code="RATE_LIMIT_EXCEEDED",
            retry_after=60,
        )

        response = _build_error_response(exc, 429)

        assert response["error"]["retry_after"] == 60

    def test_build_external_service_error_includes_service(self) -> None:
        """Test ExternalServiceError response includes service name."""
        exc = ExternalServiceError(
            message="Service unavailable",
            code="SERVICE_ERROR",
            service="OpenAlex",
        )

        response = _build_error_response(exc, 502)

        assert response["error"]["service"] == "OpenAlex"


class TestDomainErrorHandler:
    """Test domain error handler middleware."""

    @pytest.mark.asyncio
    async def test_handler_returns_correct_status_code(self) -> None:
        """Test handler returns mapped HTTP status code."""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url.path = "/test"
        request.headers.get = Mock(return_value=None)

        exc = NotFoundError(resource_type="Document", resource_id="123")

        response = await domain_error_handler(request, exc)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_handler_includes_error_in_body(self) -> None:
        """Test handler includes error details in response body."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.url.path = "/api/documents"
        request.headers.get = Mock(return_value=None)

        exc = ValidationError(
            message="Invalid input",
            code="VALIDATION_FAILED",
            field="title",
        )

        response = await domain_error_handler(request, exc)

        assert response.status_code == 422
        # Response body is JSON string, need to decode
        import json

        body = json.loads(response.body.decode())
        assert body["error"]["code"] == "VALIDATION_FAILED"
        assert body["error"]["field"] == "title"

    @pytest.mark.asyncio
    async def test_handler_adds_retry_after_header(self) -> None:
        """Test handler adds Retry-After header for rate limit errors."""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/search"
        request.headers.get = Mock(return_value=None)

        exc = RateLimitError(
            message="Rate limit exceeded",
            code="RATE_LIMIT",
            retry_after=120,
        )

        response = await domain_error_handler(request, exc)

        assert response.status_code == 429
        assert response.headers.get("Retry-After") == "120"

    @pytest.mark.asyncio
    async def test_handler_propagates_trace_id_from_request(self) -> None:
        """Test handler includes trace ID from request headers."""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url.path = "/api/test"
        request.headers.get = Mock(
            side_effect=lambda key: "trace-abc" if key == TRACE_ID_HEADER_NAME else None
        )

        exc = DomainError(message="Error", code="ERROR")

        response = await domain_error_handler(request, exc)

        assert TRACE_ID_HEADER_NAME in response.headers


class TestErrorHandlerIntegration:
    """Integration tests for error handlers with FastAPI application."""

    def test_not_found_error_returns_404(self, api_test_client: TestClient) -> None:
        """Test that NotFoundError in route handler returns 404."""
        response = api_test_client.get("/documents/non-existent-document-id")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "RETRIEVAL_DOCUMENT_NOT_FOUND"

    def test_validation_error_structure(self, api_test_client: TestClient) -> None:
        """Test validation error response structure."""
        # Try to create with invalid limit
        response = api_test_client.get("/documents/", params={"limit": -1})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data  # FastAPI validation errors use "detail"

    def test_error_includes_trace_id(self, api_test_client: TestClient) -> None:
        """Test that error responses include trace ID for observability."""
        response = api_test_client.get(
            "/documents/non-existent",
            headers={TRACE_ID_HEADER_NAME: "test-trace-123"},
        )

        assert response.status_code == 404
        # Trace ID should be in response body or headers
        data = response.json()
        has_trace_id = (
            "trace_id" in data or TRACE_ID_HEADER_NAME in response.headers
        )
        assert has_trace_id

    def test_server_error_logs_appropriately(
        self, api_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that 5xx errors are logged at ERROR level."""
        # This test would require injecting a failure into a route
        # and verifying logging output, which is complex
        # Placeholder for when implementing observability tests
        pass

    def test_client_error_logs_appropriately(
        self, api_test_client: TestClient
    ) -> None:
        """Test that 4xx errors are logged at WARNING level."""
        # Similar to above - placeholder for observability tests
        pass


class TestSpecificErrorTypes:
    """Test handling of specific domain error types."""

    def test_authorization_error_handling(self) -> None:
        """Test AuthorizationError produces 403 response."""
        exc = AuthorizationError(
            message="Access denied",
            code="FORBIDDEN",
        )

        status_code = ERROR_STATUS_MAP.get(type(exc))
        assert status_code == 403

    def test_conflict_error_handling(self) -> None:
        """Test ConflictError produces 409 response."""
        exc = ConflictError(
            message="Resource already exists",
            code="CONFLICT",
        )

        status_code = ERROR_STATUS_MAP.get(type(exc))
        assert status_code == 409

    def test_external_service_error_handling(self) -> None:
        """Test ExternalServiceError produces 502 response."""
        exc = ExternalServiceError(
            message="External API failed",
            code="EXTERNAL_ERROR",
            service="ThirdPartyAPI",
        )

        status_code = ERROR_STATUS_MAP.get(type(exc))
        assert status_code == 502

        response = _build_error_response(exc, status_code)
        assert response["error"]["service"] == "ThirdPartyAPI"


class TestErrorResponseConsistency:
    """Test that all error responses follow consistent structure."""

    def test_all_error_responses_have_error_key(self) -> None:
        """Test that error responses always have 'error' key."""
        errors = [
            NotFoundError(resource_type="Doc", resource_id="123"),
            ValidationError(message="Invalid", code="VAL", field="test"),
            AuthorizationError(message="Forbidden", code="AUTH"),
            RateLimitError(message="Too many", code="RATE", retry_after=60),
        ]

        for exc in errors:
            response = _build_error_response(exc, 400)
            assert "error" in response

    def test_all_error_responses_have_required_fields(self) -> None:
        """Test that error responses have type, code, and message."""
        exc = DomainError(message="Test error", code="TEST")
        response = _build_error_response(exc, 500)

        assert "error" in response
        assert "type" in response["error"]
        assert "code" in response["error"]
        assert "message" in response["error"]

    def test_error_response_json_serializable(self) -> None:
        """Test that error responses are JSON serializable."""
        import json

        exc = NotFoundError(
            resource_type="Document",
            resource_id="123",
            details={"reason": "deleted"},
        )

        response = _build_error_response(exc, 404, trace_id="trace-123")

        # Should not raise
        json_str = json.dumps(response)
        assert json_str


class TestUnhandledExceptions:
    """Test handling of unhandled/unexpected exceptions."""

    def test_unhandled_exception_returns_500(
        self, api_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that unhandled exceptions return 500."""

        def _raise_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        # Patch a retrieval function to raise
        monkeypatch.setattr(
            "theo.infrastructure.api.app.retriever.documents.list_documents",
            _raise_error,
        )

        response = api_test_client.get("/documents/")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data or "error" in data

    def test_unhandled_exception_includes_trace_id(
        self, api_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that unhandled exceptions include trace ID for debugging."""

        def _raise_error(*args, **kwargs):
            raise ValueError("Unexpected value error")

        monkeypatch.setattr(
            "theo.infrastructure.api.app.retriever.documents.get_document",
            _raise_error,
        )
        monkeypatch.setattr(
            "theo.infrastructure.api.app.bootstrap.middleware.get_current_trace_headers",
            lambda: {TRACE_ID_HEADER_NAME: "trace-500"},
        )

        response = api_test_client.get("/documents/test-doc")

        assert response.status_code == 500
        # Should include trace ID for debugging
        has_trace = TRACE_ID_HEADER_NAME in response.headers or "trace_id" in response.json()
        assert has_trace
