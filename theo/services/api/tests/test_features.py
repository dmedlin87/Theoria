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
        assert "creator_verse_perspectives" in payload
        assert isinstance(payload["creator_verse_perspectives"], bool)


def test_discovery_endpoint_includes_creator_verse_flag():
    with TestClient(app) as client:
        response = client.get("/features/discovery")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert "features" in payload
        features = payload["features"]
        assert "creator_verse_perspectives" in features
        assert isinstance(features["creator_verse_perspectives"], bool)
