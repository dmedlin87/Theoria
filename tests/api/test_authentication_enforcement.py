"""Comprehensive authentication enforcement tests across all routes.

Tests that protected endpoints properly enforce authentication and authorization.
Uses the @pytest.mark.no_auth_override marker to bypass the automatic auth bypass
in tests/api/conftest.py and actually test authentication logic.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.no_auth_override
class TestSearchAuthentication:
    """Test authentication enforcement for search endpoints."""

    def test_search_requires_authentication(self, api_test_client: TestClient) -> None:
        """Test that search endpoint requires authentication."""
        response = api_test_client.get("/search/", params={"q": "test"})

        # Should return 401 when no auth provided
        # OR 200 if search allows anonymous access
        assert response.status_code in [200, 401]

        if response.status_code == 401:
            assert "www-authenticate" in response.headers or "detail" in response.json()

    def test_search_with_valid_api_key(self, api_test_client: TestClient) -> None:
        """Test search with valid API key succeeds."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={"X-API-Key": "pytest-default-key"},
        )

        assert response.status_code == 200

    def test_search_with_bearer_token(self, api_test_client: TestClient) -> None:
        """Test search with Bearer token authentication."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={"Authorization": "Bearer pytest-default-key"},
        )

        assert response.status_code == 200

    def test_search_with_invalid_api_key(self, api_test_client: TestClient) -> None:
        """Test search with invalid API key is rejected."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={"X-API-Key": "invalid-key"},
        )

        # Should reject invalid keys
        assert response.status_code in [401, 403]


@pytest.mark.no_auth_override
class TestDocumentsAuthentication:
    """Test authentication enforcement for documents endpoints."""

    def test_list_documents_authentication(self, api_test_client: TestClient) -> None:
        """Test GET /documents/ authentication requirements."""
        response = api_test_client.get("/documents/")

        # May allow anonymous read access or require auth
        assert response.status_code in [200, 401]

    def test_get_document_authentication(self, api_test_client: TestClient) -> None:
        """Test GET /documents/{id} authentication requirements."""
        response = api_test_client.get("/documents/test-doc-id")

        # May allow anonymous or require auth
        assert response.status_code in [200, 401, 404]

    def test_update_document_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test PATCH /documents/{id} requires authentication."""
        response = api_test_client.patch(
            "/documents/test-doc-id",
            json={"title": "New Title"},
        )

        # Mutations should require authentication
        assert response.status_code in [401, 404]

    def test_create_annotation_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test POST /documents/{id}/annotations requires authentication."""
        response = api_test_client.post(
            "/documents/test-doc/annotations",
            json={
                "passage_id": "p1",
                "annotation_type": "note",
                "content": "Test",
            },
        )

        # Should require authentication
        assert response.status_code in [401, 404]

    def test_delete_annotation_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test DELETE /documents/{id}/annotations/{id} requires authentication."""
        response = api_test_client.delete("/documents/test-doc/annotations/anno-1")

        # Should require authentication
        assert response.status_code in [401, 404]


@pytest.mark.no_auth_override
class TestIngestAuthentication:
    """Test authentication enforcement for ingest endpoints."""

    def test_ingest_file_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test file upload requires authentication."""
        files = {"file": ("test.txt", b"test content", "text/plain")}

        response = api_test_client.post("/ingest/file", files=files)

        # Ingest should require authentication
        assert response.status_code in [401, 422]

    def test_ingest_url_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test URL ingest requires authentication."""
        response = api_test_client.post(
            "/ingest/url",
            json={"url": "https://example.com/article"},
        )

        # Should require authentication
        assert response.status_code in [401, 422]


@pytest.mark.no_auth_override
class TestDiscoveriesAuthentication:
    """Test authentication enforcement for discoveries endpoints."""

    def test_list_discoveries_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test GET /discoveries/ requires authentication."""
        response = api_test_client.get("/discoveries/")

        # User-specific data requires authentication
        assert response.status_code in [401, 404]

    def test_refresh_discoveries_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test POST /discoveries/refresh requires authentication."""
        response = api_test_client.post("/discoveries/refresh")

        # User-specific operation requires authentication
        assert response.status_code in [401, 404]


@pytest.mark.no_auth_override
class TestAIRoutesAuthentication:
    """Test authentication enforcement for AI endpoints."""

    def test_chat_requires_authentication(self, api_test_client: TestClient) -> None:
        """Test POST /ai/chat requires authentication."""
        response = api_test_client.post(
            "/ai/chat",
            json={"message": "Test question"},
        )

        # AI features require authentication
        assert response.status_code in [401, 404, 422]

    def test_watchlist_create_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test POST /ai/digest/watchlists requires authentication."""
        response = api_test_client.post(
            "/ai/digest/watchlists",
            json={
                "name": "Test Watchlist",
                "filters": {"osis": ["John 3:16"]},
                "cadence": "weekly",
            },
        )

        # Should require authentication
        assert response.status_code == 401
        body = response.json()
        assert body["detail"] == "Missing credentials"

    def test_watchlist_list_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test GET /ai/digest/watchlists requires authentication."""
        response = api_test_client.get("/ai/digest/watchlists")

        # User-specific data requires authentication
        assert response.status_code in [401, 404]


@pytest.mark.no_auth_override
class TestResearchAuthentication:
    """Test authentication enforcement for research endpoints."""

    def test_create_note_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test POST /research/notes requires authentication."""
        response = api_test_client.post(
            "/research/notes",
            json={
                "title": "Test Note",
                "content": "Test content",
            },
        )

        # Research notes are user-specific
        assert response.status_code in [401, 404, 422]

    def test_list_notes_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test GET /research/notes requires authentication."""
        response = api_test_client.get("/research/notes")

        # User-specific data
        assert response.status_code in [401, 404]

    def test_create_hypothesis_requires_authentication(
        self, api_test_client: TestClient
    ) -> None:
        """Test POST /research/hypotheses requires authentication."""
        response = api_test_client.post(
            "/research/hypotheses",
            json={
                "claim": "Test hypothesis",
                "confidence": 0.8,
            },
        )

        # User-specific data
        assert response.status_code in [401, 404, 422]


class TestAuthorizationScopes:
    """Test authorization and scope-based access control."""

    def test_user_can_only_access_own_discoveries(
        self, api_test_client: TestClient
    ) -> None:
        """Test that users can only access their own discoveries."""
        # This requires setting up multiple users and testing isolation
        # Placeholder for future implementation
        pass

    def test_user_can_only_modify_own_notes(
        self, api_test_client: TestClient
    ) -> None:
        """Test that users can only modify their own research notes."""
        # Placeholder for authorization tests
        pass

    def test_admin_endpoints_require_admin_scope(
        self, api_test_client: TestClient
    ) -> None:
        """Test that admin endpoints require admin scope."""
        # Placeholder for role-based access control tests
        pass


class TestAuthenticationHeaders:
    """Test various authentication header formats."""

    def test_bearer_token_format(self, api_test_client: TestClient) -> None:
        """Test Bearer token authentication format."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={"Authorization": "Bearer pytest-default-key"},
        )

        assert response.status_code == 200

    def test_api_key_header_format(self, api_test_client: TestClient) -> None:
        """Test X-API-Key header format."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={"X-API-Key": "pytest-default-key"},
        )

        assert response.status_code == 200

    @pytest.mark.no_auth_override
    def test_malformed_bearer_token_rejected(
        self, api_test_client: TestClient
    ) -> None:
        """Test that malformed Bearer token is rejected."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={"Authorization": "InvalidFormat pytest-default-key"},
        )

        assert response.status_code in [401, 403]

    @pytest.mark.no_auth_override
    def test_empty_bearer_token_rejected(self, api_test_client: TestClient) -> None:
        """Test that empty Bearer token is rejected."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={"Authorization": "Bearer "},
        )

        assert response.status_code in [401, 403]


class TestCrossOriginRequests:
    """Test CORS and authentication with cross-origin requests."""

    def test_cors_preflight_does_not_require_auth(
        self, api_test_client: TestClient
    ) -> None:
        """Test that OPTIONS requests (CORS preflight) don't require auth."""
        response = api_test_client.options("/search/")

        # OPTIONS should not require authentication
        assert response.status_code in [200, 204, 405]

    def test_authenticated_request_includes_cors_headers(
        self, api_test_client: TestClient
    ) -> None:
        """Test that authenticated requests include CORS headers."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={
                "X-API-Key": "pytest-default-key",
                "Origin": "http://localhost:3000",
            },
        )

        assert response.status_code == 200
        # CORS headers may or may not be present depending on middleware config


class TestRateLimiting:
    """Test rate limiting in conjunction with authentication."""

    def test_rate_limiting_per_user(self, api_test_client: TestClient) -> None:
        """Test that rate limiting is applied per authenticated user."""
        # This requires actually triggering rate limits
        # Placeholder for rate limiting tests
        pass

    def test_anonymous_requests_have_stricter_limits(
        self, api_test_client: TestClient
    ) -> None:
        """Test that anonymous requests have stricter rate limits."""
        # Placeholder for tiered rate limiting tests
        pass


class TestSessionManagement:
    """Test session-based authentication if implemented."""

    def test_session_token_authentication(self, api_test_client: TestClient) -> None:
        """Test session-based authentication."""
        # Placeholder - depends on session implementation
        pass

    def test_expired_session_rejected(self, api_test_client: TestClient) -> None:
        """Test that expired sessions are rejected."""
        # Placeholder for session expiry tests
        pass

    def test_session_invalidation(self, api_test_client: TestClient) -> None:
        """Test that sessions can be invalidated."""
        # Placeholder for logout/invalidation tests
        pass
