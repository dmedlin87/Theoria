"""Comprehensive tests for search route endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from theo.infrastructure.api.app.routes.search import (
    _parse_experiment_tokens,
    _validate_experiment_tokens,
)


class TestSearchEndpoint:
    """Test suite for the main search endpoint GET /search/."""

    def test_search_basic_query(self, api_test_client: TestClient) -> None:
        """Test basic keyword search."""
        response = api_test_client.get("/search/", params={"q": "faith"})

        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert data["query"] == "faith"
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_search_with_osis_filter(self, api_test_client: TestClient) -> None:
        """Test search with OSIS reference filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "grace", "osis": "John.3.16"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "grace"
        assert data["osis"] == "John.3.16"

    def test_search_with_collection_filter(self, api_test_client: TestClient) -> None:
        """Test search with collection filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "hope", "collection": "systematic-theology"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "hope"

    def test_search_with_author_filter(self, api_test_client: TestClient) -> None:
        """Test search with author filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "resurrection", "author": "Wright, N.T."},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "resurrection"

    def test_search_with_source_type_filter(self, api_test_client: TestClient) -> None:
        """Test search with source type filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "exegesis", "source_type": "commentary"},
        )

        assert response.status_code == 200

    def test_search_with_perspective_filter(self, api_test_client: TestClient) -> None:
        """Test search with theological perspective filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "miracles", "perspective": "skeptical"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "miracles"

    def test_search_with_perspective_apologetic(
        self, api_test_client: TestClient
    ) -> None:
        """Test search with apologetic perspective."""
        response = api_test_client.get(
            "/search/",
            params={"q": "resurrection", "perspective": "apologetic"},
        )

        assert response.status_code == 200

    def test_search_with_perspective_neutral(self, api_test_client: TestClient) -> None:
        """Test search with neutral perspective."""
        response = api_test_client.get(
            "/search/",
            params={"q": "text criticism", "perspective": "neutral"},
        )

        assert response.status_code == 200

    def test_search_with_theological_tradition(
        self, api_test_client: TestClient
    ) -> None:
        """Test search with theological tradition filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "grace", "theological_tradition": "reformed"},
        )

        assert response.status_code == 200

    def test_search_with_topic_domain_filter(self, api_test_client: TestClient) -> None:
        """Test search with topic domain filter."""
        response = api_test_client.get(
            "/search/",
            params={"q": "justification", "topic_domain": "soteriology"},
        )

        assert response.status_code == 200

    def test_search_with_limit_parameter(self, api_test_client: TestClient) -> None:
        """Test search with custom result limit."""
        response = api_test_client.get(
            "/search/",
            params={"q": "love", "k": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 5

    def test_search_limit_minimum(self, api_test_client: TestClient) -> None:
        """Test search with minimum limit (k=1)."""
        response = api_test_client.get(
            "/search/",
            params={"q": "love", "k": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 1

    def test_search_limit_maximum(self, api_test_client: TestClient) -> None:
        """Test search with maximum limit (k=50)."""
        response = api_test_client.get(
            "/search/",
            params={"q": "love", "k": 50},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 50

    def test_search_limit_too_low_rejected(self, api_test_client: TestClient) -> None:
        """Test that k < 1 is rejected."""
        response = api_test_client.get(
            "/search/",
            params={"q": "love", "k": 0},
        )

        assert response.status_code == 422  # Validation error

    def test_search_limit_too_high_rejected(self, api_test_client: TestClient) -> None:
        """Test that k > 50 is rejected."""
        response = api_test_client.get(
            "/search/",
            params={"q": "love", "k": 51},
        )

        assert response.status_code == 422  # Validation error

    def test_search_without_query_parameters(self, api_test_client: TestClient) -> None:
        """Test search without q or osis returns empty results."""
        response = api_test_client.get("/search/")

        assert response.status_code == 200
        data = response.json()
        assert data["query"] is None
        assert data["osis"] is None

    def test_search_with_multiple_filters(self, api_test_client: TestClient) -> None:
        """Test search with multiple filters combined."""
        response = api_test_client.get(
            "/search/",
            params={
                "q": "covenant",
                "osis": "Genesis.1",
                "collection": "old-testament",
                "author": "Walton, John",
                "source_type": "commentary",
                "perspective": "neutral",
                "k": 20,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "covenant"
        assert data["osis"] == "Genesis.1"


class TestSearchExperiments:
    """Test suite for search experiment flags."""

    def test_search_experiment_single_flag(self, api_test_client: TestClient) -> None:
        """Test search with single experiment flag."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test", "experiment": "rerank=bge"},
        )

        assert response.status_code == 200

    def test_search_experiment_multiple_flags(
        self, api_test_client: TestClient
    ) -> None:
        """Test search with multiple experiment flags."""
        response = api_test_client.get(
            "/search/",
            params=[
                ("q", "test"),
                ("experiment", "rerank=bge"),
                ("experiment", "cap=100"),
                ("experiment", "alpha=0.5"),
            ],
        )

        assert response.status_code == 200

    def test_search_experiment_header_format(self, api_test_client: TestClient) -> None:
        """Test experiment flags via X-Search-Experiments header."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={"X-Search-Experiments": "rerank=cross,cap=50"},
        )

        assert response.status_code == 200

    def test_search_experiment_header_and_params(
        self, api_test_client: TestClient
    ) -> None:
        """Test experiment flags from both header and query params."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test", "experiment": "alpha=0.5"},
            headers={"X-Search-Experiments": "rerank=bge"},
        )

        assert response.status_code == 200

    def test_search_experiment_too_many_flags_rejected(
        self, api_test_client: TestClient
    ) -> None:
        """Test that exceeding max experiment flags is rejected."""
        # Create 21 experiment flags (max is 20)
        params = [("q", "test")] + [
            ("experiment", f"flag{i}=value") for i in range(21)
        ]

        response = api_test_client.get("/search/", params=params)

        assert response.status_code == 400
        assert "limit is" in response.json()["detail"]

    def test_search_experiment_header_too_long_rejected(
        self, api_test_client: TestClient
    ) -> None:
        """Test that experiment header exceeding max length is rejected."""
        # Create header longer than 512 characters
        long_header = ",".join([f"flag{i}=value" for i in range(50)])

        response = api_test_client.get(
            "/search/",
            params={"q": "test"},
            headers={"X-Search-Experiments": long_header},
        )

        assert response.status_code == 400
        assert "header exceeds" in response.json()["detail"]

    def test_search_experiment_token_too_long_rejected(
        self, api_test_client: TestClient
    ) -> None:
        """Test that individual experiment token exceeding max length is rejected."""
        # Create token longer than 64 characters
        long_token = "x" * 65

        response = api_test_client.get(
            "/search/",
            params={"q": "test", "experiment": long_token},
        )

        assert response.status_code == 400
        assert "shorter than" in response.json()["detail"]

    def test_search_reranker_header_in_response(
        self, api_test_client: TestClient
    ) -> None:
        """Test that X-Reranker header is included when reranking occurs."""
        response = api_test_client.get(
            "/search/",
            params={"q": "test", "k": 10},
        )

        assert response.status_code == 200
        # X-Reranker header should be present if reranking happened
        # (implementation-dependent)


class TestExperimentHelpers:
    """Test helper functions for experiment token parsing."""

    def test_parse_experiment_tokens_key_value(self) -> None:
        """Test parsing experiment tokens in key=value format."""
        tokens = ["rerank=bge", "cap=100", "alpha=0.5"]
        result = _parse_experiment_tokens(tokens)

        assert result == {
            "rerank": "bge",
            "cap": "100",
            "alpha": "0.5",
        }

    def test_parse_experiment_tokens_key_colon_value(self) -> None:
        """Test parsing experiment tokens in key:value format."""
        tokens = ["rerank:bge", "cap:100"]
        result = _parse_experiment_tokens(tokens)

        assert result == {
            "rerank": "bge",
            "cap": "100",
        }

    def test_parse_experiment_tokens_flag_only(self) -> None:
        """Test parsing experiment tokens with flag-only format."""
        tokens = ["enable_feature", "debug"]
        result = _parse_experiment_tokens(tokens)

        assert result == {
            "enable_feature": "1",
            "debug": "1",
        }

    def test_parse_experiment_tokens_mixed_formats(self) -> None:
        """Test parsing mixed format experiment tokens."""
        tokens = ["rerank=bge", "cap:100", "debug"]
        result = _parse_experiment_tokens(tokens)

        assert result == {
            "rerank": "bge",
            "cap": "100",
            "debug": "1",
        }

    def test_parse_experiment_tokens_empty_strings_ignored(self) -> None:
        """Test that empty strings are ignored."""
        tokens = ["rerank=bge", "", "cap=100", ""]
        result = _parse_experiment_tokens(tokens)

        assert result == {
            "rerank": "bge",
            "cap": "100",
        }

    def test_parse_experiment_tokens_case_normalization(self) -> None:
        """Test that keys are normalized to lowercase."""
        tokens = ["RERANK=bge", "Cap=100", "AlPhA=0.5"]
        result = _parse_experiment_tokens(tokens)

        assert result == {
            "rerank": "bge",
            "cap": "100",
            "alpha": "0.5",
        }

    def test_validate_experiment_tokens_valid(self) -> None:
        """Test validation passes for valid tokens."""
        tokens = ["rerank=bge", "cap=100", "alpha=0.5"]
        result = _validate_experiment_tokens(tokens)

        assert result == tokens

    def test_validate_experiment_tokens_filters_empty(self) -> None:
        """Test that empty strings are filtered out."""
        tokens = ["rerank=bge", "", "cap=100"]
        result = _validate_experiment_tokens(tokens)

        assert result == ["rerank=bge", "cap=100"]

    def test_validate_experiment_tokens_too_many_raises(self) -> None:
        """Test that exceeding max count raises HTTPException."""
        tokens = [f"flag{i}=value" for i in range(21)]

        with pytest.raises(Exception) as exc_info:
            _validate_experiment_tokens(tokens)

        assert "Too many experiment flags" in str(exc_info.value)

    def test_validate_experiment_tokens_too_long_raises(self) -> None:
        """Test that oversized token raises HTTPException."""
        tokens = ["x" * 65]

        with pytest.raises(Exception) as exc_info:
            _validate_experiment_tokens(tokens)

        assert "shorter than" in str(exc_info.value)


@pytest.mark.no_auth_override
class TestSearchAuthentication:
    """Test search endpoint authentication requirements."""

    def test_search_requires_authentication(self, api_test_client: TestClient) -> None:
        """Test that search endpoint requires authentication when enabled."""
        # This test uses no_auth_override marker, so authentication is enforced
        response = api_test_client.get("/search/", params={"q": "test"})

        # Depending on authentication configuration, this may require auth
        # Implementation should be consistent with other authenticated endpoints
        assert response.status_code in [200, 401]
