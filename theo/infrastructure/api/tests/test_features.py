"""Tests for feature flag discovery endpoint."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from theo.infrastructure.api.app.main import app


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


def _set_feature_flags(monkeypatch, **overrides: bool) -> None:
    from theo.infrastructure.api.app.routes import features as features_routes

    monkeypatch.setattr(
        features_routes,
        "get_settings",
        lambda: _mock_settings(**overrides),
        raising=False,
    )


def _get_json(path: str) -> dict[str, object]:
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def test_features_endpoint_respects_optional_flags(monkeypatch):
    _set_feature_flags(
        monkeypatch,
        gpt5_codex_preview_enabled=True,
        verse_timeline_enabled=True,
    )
    enabled_payload = _get_json("/features")
    assert enabled_payload == {
        "gpt5_codex_preview": True,
        "job_tracking": True,
        "document_annotations": True,
        "ai_copilot": True,
        "cross_references": True,
        "textual_variants": True,
        "morphology": True,
        "commentaries": True,
        "verse_timeline": True,
    }

    _set_feature_flags(
        monkeypatch,
        gpt5_codex_preview_enabled=False,
        verse_timeline_enabled=False,
    )
    disabled_payload = _get_json("/features")
    assert disabled_payload == {
        "gpt5_codex_preview": False,
        "job_tracking": True,
        "document_annotations": True,
        "ai_copilot": True,
        "cross_references": True,
        "textual_variants": True,
        "morphology": True,
        "commentaries": True,
        "verse_timeline": False,
    }
    assert enabled_payload != disabled_payload


def test_discovery_endpoint_respects_optional_flags(monkeypatch):
    _set_feature_flags(
        monkeypatch,
        contradictions_enabled=True,
        geo_enabled=True,
        creator_verse_perspectives_enabled=True,
        verse_timeline_enabled=True,
    )
    enabled_features = _get_json("/features/discovery")["features"]
    assert enabled_features == {
        "research": True,
        "contradictions": True,
        "geo": True,
        "cross_references": True,
        "textual_variants": True,
        "morphology": True,
        "commentaries": True,
        "creator_verse_perspectives": True,
        "verse_timeline": True,
    }

    _set_feature_flags(
        monkeypatch,
        contradictions_enabled=False,
        geo_enabled=False,
        creator_verse_perspectives_enabled=False,
        verse_timeline_enabled=False,
    )
    disabled_features = _get_json("/features/discovery")["features"]
    assert disabled_features == {
        "research": True,
        "contradictions": False,
        "geo": False,
        "cross_references": True,
        "textual_variants": True,
        "morphology": True,
        "commentaries": True,
        "creator_verse_perspectives": False,
        "verse_timeline": False,
    }
    assert enabled_features != disabled_features
