from __future__ import annotations

from fastapi.testclient import TestClient

from theo.services.api.app.main import app


def _create_note(client: TestClient, **overrides: object) -> dict:
    payload = {
        "osis": "John.1.1",
        "body": "Default note body",
        "stance": None,
        "claim_type": None,
        "confidence": None,
        "tags": None,
    }
    payload.update(overrides)
    response = client.post("/research/notes", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["note"]


def test_list_notes_basic_retrieval() -> None:
    with TestClient(app) as client:
        created = _create_note(
            client,
            osis="Acts.1.1",
            body="Opening line observations",
            stance="neutral",
        )

        response = client.get("/research/notes", params={"osis": "Acts.1.1"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["notes"][0]["id"] == created["id"]


def test_list_notes_stance_filter_case_insensitive() -> None:
    with TestClient(app) as client:
        _create_note(
            client,
            osis="Romans.1.1",
            body="Affirming Paul's apostleship",
            stance="supportive",
        )
        _create_note(
            client,
            osis="Romans.1.1",
            body="Questioning Paul's authorship",
            stance="critical",
        )

        response = client.get(
            "/research/notes",
            params={"osis": "Romans.1.1", "stance": "SUPPORTIVE"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["notes"][0]["stance"] == "supportive"


def test_list_notes_tag_filter() -> None:
    with TestClient(app) as client:
        _create_note(
            client,
            osis="Mark.1.1",
            body="Prologue overview",
            tags=["intro", "gospel"],
        )
        _create_note(
            client,
            osis="Mark.1.1",
            body="Secondary note",
            tags=["summary"],
        )

        response = client.get(
            "/research/notes",
            params={"osis": "Mark.1.1", "tag": "gospel"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["notes"][0]["tags"] == ["intro", "gospel"]


def test_list_notes_combined_filters() -> None:
    with TestClient(app) as client:
        matching = _create_note(
            client,
            osis="Luke.1.1",
            body="Detailed investigation",
            stance="investigative",
            claim_type="historical",
            confidence=0.85,
            tags=["preface", "orderly"],
        )
        _create_note(
            client,
            osis="Luke.1.1",
            body="Lower confidence note",
            stance="investigative",
            claim_type="historical",
            confidence=0.4,
            tags=["preface"],
        )
        _create_note(
            client,
            osis="Luke.1.1",
            body="Different stance",
            stance="devotional",
            claim_type="theological",
            confidence=0.9,
            tags=["preface", "orderly"],
        )

        response = client.get(
            "/research/notes",
            params={
                "osis": "Luke.1.1",
                "stance": "INVESTIGATIVE",
                "claim_type": "Historical",
                "tag": "orderly",
                "min_confidence": 0.75,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["notes"][0]["id"] == matching["id"]


def test_list_notes_invalid_min_confidence() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/notes",
            params={"osis": "John.3.16", "min_confidence": 1.5},
        )
        assert response.status_code == 422


def test_list_notes_empty_results_when_filters_no_match() -> None:
    with TestClient(app) as client:
        _create_note(
            client,
            osis="Matthew.1.1",
            body="Genealogy reflection",
            stance="affirming",
        )

        response = client.get(
            "/research/notes",
            params={"osis": "Matthew.1.1", "stance": "critical"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 0
        assert payload["notes"] == []
