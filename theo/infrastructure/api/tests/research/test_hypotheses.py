"""Tests for the research hypotheses API routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from theo.infrastructure.api.app.main import app


def _create_hypothesis(client: TestClient, **overrides: object) -> dict:
    payload = {
        "claim": "Paul authored Hebrews",
        "confidence": 0.4,
        "status": "active",
        "supporting_passage_ids": ["passage-a"],
    }
    payload.update(overrides)
    response = client.post("/research/hypotheses", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["hypothesis"]


def test_create_and_list_hypotheses() -> None:
    with TestClient(app) as client:
        created = _create_hypothesis(
            client,
            claim="The prologue reflects temple liturgy",
            status="confirmed",
            confidence=0.82,
            perspective_scores={"skeptical": 0.2, "apologetic": 0.8},
        )

        response = client.get("/research/hypotheses")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["hypotheses"][0]["id"] == created["id"]
        assert payload["hypotheses"][0]["perspective_scores"]["apologetic"] == 0.8


def test_list_hypotheses_supports_filters() -> None:
    with TestClient(app) as client:
        _create_hypothesis(
            client,
            claim="Luke used Mark",
            status="confirmed",
            confidence=0.9,
        )
        _create_hypothesis(
            client,
            claim="Q source underlies synoptics",
            status="active",
            confidence=0.55,
        )
        _create_hypothesis(
            client,
            claim="Late authorship of Daniel",
            status="refuted",
            confidence=0.15,
        )

        response = client.get(
            "/research/hypotheses",
            params={"status": ["confirmed"], "min_confidence": 0.8, "q": "luke"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["hypotheses"][0]["claim"].lower().startswith("luke")


def test_update_hypothesis_changes_status_and_confidence() -> None:
    with TestClient(app) as client:
        hypothesis = _create_hypothesis(client, claim="Peter led the Jerusalem council")

        response = client.patch(
            f"/research/hypotheses/{hypothesis['id']}",
            json={"status": "refuted", "confidence": 0.1},
        )
        assert response.status_code == 200
        payload = response.json()["hypothesis"]
        assert payload["status"] == "refuted"
        assert payload["confidence"] == 0.1


def test_update_unknown_hypothesis_returns_not_found() -> None:
    with TestClient(app) as client:
        response = client.patch(
            "/research/hypotheses/unknown-id",
            json={"status": "confirmed"},
        )
        assert response.status_code == 404
