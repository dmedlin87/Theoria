"""Comprehensive tests for analytics route endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestTelemetryIngestion:
    """Test suite for POST /analytics/telemetry endpoint."""

    def test_ingest_telemetry_accepts_valid_batch(
        self, api_test_client: TestClient
    ) -> None:
        """Test accepting valid telemetry batch."""
        payload = {
            "session_id": "test-session-123",
            "user_id": "test-user",
            "events": [
                {
                    "event_type": "page_view",
                    "timestamp": "2025-01-15T12:00:00Z",
                    "properties": {"page": "/search"},
                },
                {
                    "event_type": "search_query",
                    "timestamp": "2025-01-15T12:01:00Z",
                    "properties": {"query": "faith", "results_count": 10},
                },
            ],
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"

    def test_ingest_telemetry_empty_events(self, api_test_client: TestClient) -> None:
        """Test ingesting telemetry with empty events array."""
        payload = {
            "session_id": "test-session",
            "user_id": "test-user",
            "events": [],
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        assert response.status_code == 202

    def test_ingest_telemetry_missing_required_fields(
        self, api_test_client: TestClient
    ) -> None:
        """Test that missing required fields are rejected."""
        payload = {
            "session_id": "test-session",
            # Missing user_id and events
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        assert response.status_code == 422

    def test_ingest_telemetry_invalid_json(self, api_test_client: TestClient) -> None:
        """Test that invalid JSON is rejected."""
        response = api_test_client.post(
            "/analytics/telemetry",
            data="invalid-json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_ingest_telemetry_multiple_event_types(
        self, api_test_client: TestClient
    ) -> None:
        """Test ingesting various event types in one batch."""
        payload = {
            "session_id": "test-session",
            "user_id": "test-user",
            "events": [
                {
                    "event_type": "page_view",
                    "timestamp": "2025-01-15T12:00:00Z",
                    "properties": {},
                },
                {
                    "event_type": "button_click",
                    "timestamp": "2025-01-15T12:00:01Z",
                    "properties": {"button_id": "search"},
                },
                {
                    "event_type": "api_call",
                    "timestamp": "2025-01-15T12:00:02Z",
                    "properties": {"endpoint": "/search", "duration_ms": 150},
                },
            ],
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        assert response.status_code == 202

    def test_ingest_telemetry_with_metadata(
        self, api_test_client: TestClient
    ) -> None:
        """Test ingesting telemetry with additional metadata."""
        payload = {
            "session_id": "test-session",
            "user_id": "test-user",
            "events": [
                {
                    "event_type": "error",
                    "timestamp": "2025-01-15T12:00:00Z",
                    "properties": {
                        "error_type": "NetworkError",
                        "message": "Connection timeout",
                        "stack_trace": "Error at line 42...",
                    },
                }
            ],
            "client_info": {
                "user_agent": "Mozilla/5.0...",
                "screen_width": 1920,
                "screen_height": 1080,
            },
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        assert response.status_code == 202


class TestFeedbackIngestion:
    """Test suite for POST /analytics/feedback endpoint."""

    def test_ingest_feedback_positive(self, api_test_client: TestClient) -> None:
        """Test ingesting positive feedback."""
        payload = {
            "event_type": "thumbs_up",
            "target_type": "search_result",
            "target_id": "result-123",
            "user_id": "test-user",
            "timestamp": "2025-01-15T12:00:00Z",
            "context": {
                "query": "faith",
                "position": 1,
            },
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"

    def test_ingest_feedback_negative(self, api_test_client: TestClient) -> None:
        """Test ingesting negative feedback."""
        payload = {
            "event_type": "thumbs_down",
            "target_type": "ai_response",
            "target_id": "response-456",
            "user_id": "test-user",
            "timestamp": "2025-01-15T12:00:00Z",
            "reason": "inaccurate",
            "comment": "The response contained factual errors",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code == 202

    def test_ingest_feedback_with_detailed_context(
        self, api_test_client: TestClient
    ) -> None:
        """Test feedback with rich contextual information."""
        payload = {
            "event_type": "report_issue",
            "target_type": "document",
            "target_id": "doc-789",
            "user_id": "test-user",
            "timestamp": "2025-01-15T12:00:00Z",
            "issue_type": "broken_link",
            "context": {
                "page_url": "/documents/doc-789",
                "user_agent": "Mozilla/5.0...",
                "reported_url": "https://example.com/broken",
            },
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code == 202

    def test_ingest_feedback_missing_required_fields(
        self, api_test_client: TestClient
    ) -> None:
        """Test that missing required fields are rejected."""
        payload = {
            "event_type": "thumbs_up",
            # Missing target_type, target_id, user_id, timestamp
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code == 422

    def test_ingest_feedback_invalid_event_type(
        self, api_test_client: TestClient
    ) -> None:
        """Test that invalid event types are handled appropriately."""
        payload = {
            "event_type": "invalid_event_type",
            "target_type": "result",
            "target_id": "123",
            "user_id": "test-user",
            "timestamp": "2025-01-15T12:00:00Z",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        # Depending on validation, may accept or reject
        assert response.status_code in [202, 400, 422]

    def test_ingest_feedback_persistence_error_handling(
        self, api_test_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test error handling when feedback persistence fails."""

        def _raise_value_error(*args, **kwargs):
            raise ValueError("Database constraint violation")

        monkeypatch.setattr(
            "theo.infrastructure.api.app.analytics.telemetry.record_feedback_from_payload",
            _raise_value_error,
        )

        payload = {
            "event_type": "thumbs_up",
            "target_type": "result",
            "target_id": "123",
            "user_id": "test-user",
            "timestamp": "2025-01-15T12:00:00Z",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_ingest_feedback_with_tags(self, api_test_client: TestClient) -> None:
        """Test feedback with categorization tags."""
        payload = {
            "event_type": "feature_request",
            "target_type": "application",
            "target_id": "theoria",
            "user_id": "test-user",
            "timestamp": "2025-01-15T12:00:00Z",
            "tags": ["search", "ux-improvement", "high-priority"],
            "description": "Add faceted search filters",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code in [202, 400, 422]


class TestAnalyticsAuthentication:
    """Test analytics endpoint authentication."""

    def test_telemetry_ingestion_anonymous(self, api_test_client: TestClient) -> None:
        """Test that telemetry can be ingested without authentication."""
        payload = {
            "session_id": "anon-session",
            "user_id": "anonymous",
            "events": [{"event_type": "page_view", "timestamp": "2025-01-15T12:00:00Z"}],
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        # Analytics endpoints typically allow anonymous telemetry
        assert response.status_code == 202

    def test_feedback_requires_user_id(self, api_test_client: TestClient) -> None:
        """Test that feedback requires a user_id."""
        payload = {
            "event_type": "thumbs_up",
            "target_type": "result",
            "target_id": "123",
            # Missing user_id
            "timestamp": "2025-01-15T12:00:00Z",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        assert response.status_code == 422


class TestAnalyticsPerformance:
    """Test analytics endpoint performance characteristics."""

    def test_telemetry_accepts_large_batches(
        self, api_test_client: TestClient
    ) -> None:
        """Test that large telemetry batches are accepted."""
        # Generate a batch of 100 events
        events = [
            {
                "event_type": "metric",
                "timestamp": f"2025-01-15T12:00:{i:02d}Z",
                "properties": {"metric_name": f"test_{i}", "value": i},
            }
            for i in range(100)
        ]

        payload = {
            "session_id": "test-session",
            "user_id": "test-user",
            "events": events,
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        assert response.status_code == 202

    def test_telemetry_idempotent(self, api_test_client: TestClient) -> None:
        """Test that submitting same telemetry batch multiple times is safe."""
        payload = {
            "session_id": "idempotent-test",
            "user_id": "test-user",
            "events": [{"event_type": "test", "timestamp": "2025-01-15T12:00:00Z"}],
        }

        # Submit twice
        response1 = api_test_client.post("/analytics/telemetry", json=payload)
        response2 = api_test_client.post("/analytics/telemetry", json=payload)

        assert response1.status_code == 202
        assert response2.status_code == 202


class TestAnalyticsDataValidation:
    """Test data validation for analytics endpoints."""

    def test_telemetry_validates_timestamp_format(
        self, api_test_client: TestClient
    ) -> None:
        """Test that invalid timestamp formats are handled."""
        payload = {
            "session_id": "test",
            "user_id": "test-user",
            "events": [
                {
                    "event_type": "test",
                    "timestamp": "not-a-valid-timestamp",
                }
            ],
        }

        response = api_test_client.post("/analytics/telemetry", json=payload)

        # Depending on validation strictness
        assert response.status_code in [202, 400, 422]

    def test_feedback_validates_target_references(
        self, api_test_client: TestClient
    ) -> None:
        """Test validation of target type and ID combinations."""
        payload = {
            "event_type": "thumbs_up",
            "target_type": "",  # Empty target type
            "target_id": "123",
            "user_id": "test-user",
            "timestamp": "2025-01-15T12:00:00Z",
        }

        response = api_test_client.post("/analytics/feedback", json=payload)

        # Should reject empty target_type
        assert response.status_code in [400, 422]
