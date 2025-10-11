"""Tests for feature flag discovery endpoint."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from theo.services.api.app.main import app


def _mock_settings(**overrides: bool) -> SimpleNamespace:
    defaults: dict[str, bool] = {
        "gpt5_codex_preview_enabled": True,
        "verse_timeline_enabled": True,
        "contradictions_enabled": True,
        "geo_enabled": True,
        "creator_verse_perspectives_enabled": True,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_features_endpoint_respects_optional_flags(monkeypatch):
    from theo.services.api.app.routes import features as features_routes

    enabled_settings = _mock_settings(
        gpt5_codex_preview_enabled=True, verse_timeline_enabled=True
    )
    monkeypatch.setattr(
        features_routes, "get_settings", lambda: enabled_settings, raising=False
    )

    with TestClient(app) as client:
        enabled_response = client.get("/features")
    assert enabled_response.status_code == 200, enabled_response.text
    enabled_payload = enabled_response.json()
    assert enabled_payload["gpt5_codex_preview"] is True
    assert enabled_payload["verse_timeline"] is True

    disabled_settings = _mock_settings(
        gpt5_codex_preview_enabled=False, verse_timeline_enabled=False
    )
    monkeypatch.setattr(
        features_routes, "get_settings", lambda: disabled_settings, raising=False
    )

    with TestClient(app) as client:
        disabled_response = client.get("/features")
    assert disabled_response.status_code == 200, disabled_response.text
    disabled_payload = disabled_response.json()
    assert disabled_payload["gpt5_codex_preview"] is False
    assert disabled_payload["verse_timeline"] is False
    assert enabled_payload != disabled_payload


def test_discovery_endpoint_respects_optional_flags(monkeypatch):
    from theo.services.api.app.routes import features as features_routes

    enabled_settings = _mock_settings(
        contradictions_enabled=True,
        geo_enabled=True,
        creator_verse_perspectives_enabled=True,
        verse_timeline_enabled=True,
    )
    monkeypatch.setattr(
        features_routes, "get_settings", lambda: enabled_settings, raising=False
    )

    with TestClient(app) as client:
        enabled_response = client.get("/features/discovery")
    assert enabled_response.status_code == 200, enabled_response.text
    enabled_features = enabled_response.json()["features"]
    assert enabled_features["contradictions"] is True
    assert enabled_features["geo"] is True
    assert enabled_features["creator_verse_perspectives"] is True
    assert enabled_features["verse_timeline"] is True

    disabled_settings = _mock_settings(
        contradictions_enabled=False,
        geo_enabled=False,
        creator_verse_perspectives_enabled=False,
        verse_timeline_enabled=False,
    )
    monkeypatch.setattr(
        features_routes, "get_settings", lambda: disabled_settings, raising=False
    )

    with TestClient(app) as client:
        disabled_response = client.get("/features/discovery")
    assert disabled_response.status_code == 200, disabled_response.text
    disabled_features = disabled_response.json()["features"]
    assert disabled_features["contradictions"] is False
    assert disabled_features["geo"] is False
    assert disabled_features["creator_verse_perspectives"] is False
    assert disabled_features["verse_timeline"] is False
    assert enabled_features != disabled_features
