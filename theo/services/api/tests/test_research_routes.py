from __future__ import annotations

from fastapi.testclient import TestClient

from theo.services.api.app.main import app


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
