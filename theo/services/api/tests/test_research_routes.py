from __future__ import annotations

from fastapi.testclient import TestClient

from theo.services.api.app.main import app
from theo.services.api.app.core import settings as settings_module


def test_scripture_endpoint_returns_range() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/scripture",
            params={"osis": "John.1.1-2", "translation": "ESV"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["translation"] == "ESV"
        assert payload["meta"]["count"] == 2
        assert [verse["osis"] for verse in payload["verses"]] == ["John.1.1", "John.1.2"]


def test_crossrefs_endpoint_returns_ranked_results() -> None:
    with TestClient(app) as client:
        response = client.get("/research/crossrefs", params={"osis": "John.1.1", "limit": 1})
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["results"][0]["target"] == "Genesis.1.1"


def test_morphology_endpoint_returns_tokens() -> None:
    with TestClient(app) as client:
        response = client.get("/research/morphology", params={"osis": "John.1.1"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["tokens"]
        token = payload["tokens"][0]
        assert token["surface"] == "\u1f18\u03bd"
        assert token["gloss"] == "in"


def test_notes_crud_roundtrip() -> None:
    with TestClient(app) as client:
        create = client.post(
            "/research/notes",
            json={
                "osis": "John.1.1",
                "body": "The Logos is identified with God.",
                "stance": "apologetic",
                "claim_type": "theological",
                "confidence": 0.8,
                "evidences": [
                    {
                        "source_type": "crossref",
                        "source_ref": "Genesis.1.1",
                        "snippet": "Creation prologue echoes.",
                        "osis_refs": ["Genesis.1.1"],
                    }
                ],
            },
        )
        assert create.status_code == 201
        note_id = create.json()["note"]["id"]

        listing = client.get("/research/notes", params={"osis": "John.1.1"})
        assert listing.status_code == 200
        payload = listing.json()
        assert payload["total"] == 1
        note = payload["notes"][0]
        assert note["id"] == note_id
        assert note["stance"] == "apologetic"
        assert note["evidences"][0]["source_ref"] == "Genesis.1.1"


def test_contradictions_by_osis_returns_items_and_is_stable_shape() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/contradictions",
            params=[("osis", "Luke.2.1-7"), ("topic", "chronology")],
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert "items" in payload
        assert payload["items"], "Expected seeded contradictions for Luke 2"
        first = payload["items"][0]
        assert first["osis_a"] == "Luke.2.1-7"
        assert first["osis_b"] == "Matthew.2.1-12"
        assert first["tags"] == ["chronology", "nativity"]
        assert first["weight"] >= payload["items"][1]["weight"] if len(payload["items"]) > 1 else True


def test_geo_lookup_returns_places_with_confidence_and_aliases() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/geo/search",
            params={"query": "Bethlehem"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["items"], "Expected seeded geography entries"
        place = payload["items"][0]
        assert place["slug"] == "bethlehem"
        assert place["confidence"] >= 0.9
        assert "Bethlehem Ephrathah" in place["aliases"]


def test_features_exposed_in_discovery() -> None:
    with TestClient(app) as client:
        response = client.get("/features/discovery")
        assert response.status_code == 200
        payload = response.json()
        assert payload["features"]["research"] is True
        assert isinstance(payload["features"]["contradictions"], bool)
        assert isinstance(payload["features"]["geo"], bool)


def test_flags_off_returns_empty_items_but_200() -> None:
    settings = settings_module.get_settings()
    original_contra = settings.contradictions_enabled
    original_geo = settings.geo_enabled
    settings.contradictions_enabled = False
    settings.geo_enabled = False
    try:
        with TestClient(app) as client:
            contra = client.get(
                "/research/contradictions",
                params=[("osis", "Luke.2.1-7")],
            )
            geo = client.get("/research/geo/search", params={"query": "Bethlehem"})
            assert contra.status_code == 200
            assert contra.json()["items"] == []
            assert geo.status_code == 200
            assert geo.json()["items"] == []
    finally:
        settings.contradictions_enabled = original_contra
        settings.geo_enabled = original_geo
