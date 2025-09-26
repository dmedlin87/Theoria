"""Tests for feature flag discovery endpoint."""

from fastapi.testclient import TestClient

from theo.services.api.app.main import app


def test_features_endpoint_returns_gpt5_flag():
    with TestClient(app) as client:
        response = client.get("/features")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert "gpt5_codex_preview" in payload
        assert isinstance(payload["gpt5_codex_preview"], bool)


def test_discovery_includes_creator_perspectives_flag():
    with TestClient(app) as client:
        response = client.get("/features/discovery")
        assert response.status_code == 200, response.text
        payload = response.json()
        features = payload.get("features")
        assert features is not None
        assert "creator_verse_perspectives" in features
