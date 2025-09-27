"""Tests for the creator verse perspectives endpoints."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from theo.services.api.app.main import app

SAMPLE_VTT = """WEBVTT

00:00.000 --> 00:06.000
Speaker 1: Baptism in John 3:5 points to the Spirit's work.

00:06.000 --> 00:12.000
We also draw from Matthew 28:19 to discuss discipleship.
"""


def _ingest_sample_transcript(client: TestClient, *, variant: str | None = None) -> str:
    transcript_body = SAMPLE_VTT
    if variant:
        transcript_body = SAMPLE_VTT.replace(
            "Spirit's work.", f"Spirit's work ({variant})."
        )

    frontmatter = {
        "title": "Baptism Teaching",
        "collection": "teachings",
        "creator": "Wes Huff",
        "channel": "Apologia",
        "creator_tags": ["apologetics", "youtube"],
        "creator_bio": "Apologist and teacher.",
        "video_id": "abc123",
        "source_url": "https://youtu.be/abc123",
        "published_at": "2024-05-12T00:00:00Z",
        "duration_seconds": 120,
        "topics": ["Baptism", "Grace"],
        "creator_stances": {"baptism": "for"},
        "creator_confidence": 0.75,
    }
    if variant:
        frontmatter["video_id"] = f"abc123-{variant}"
        frontmatter["source_url"] = f"https://youtu.be/abc123?variant={variant}"

    response = client.post(
        "/ingest/transcript",
        files={"transcript": ("teaching.vtt", transcript_body, "text/vtt")},
        data={"frontmatter": json.dumps(frontmatter)},
    )
    assert response.status_code == 200, response.text
    return response.json()["document_id"]


def test_creator_verse_perspectives_returns_rollup() -> None:
    with TestClient(app) as client:
        _ingest_sample_transcript(client, variant="a")

        response = client.get(
            "/creators/verses",
            params={"osis": "John.3.5", "limit_creators": 5, "limit_quotes": 2},
        )
        assert response.status_code == 200, response.text
        payload = response.json()

        assert payload["osis"] == "John.3.5"
        assert payload["total_creators"] >= 1
        assert payload["creators"], "Expected at least one creator in rollup"

        creator = payload["creators"][0]
        assert creator["creator_name"] == "Wes Huff"
        assert creator["stance"] == "for"
        assert creator["stance_counts"]["for"] >= 1
        assert creator["claim_count"] >= 1
        assert creator["quotes"], "Expected quotes in creator perspective"
        quote = creator["quotes"][0]
        assert quote["quote_md"]
        assert quote["video"] is not None
        assert quote["video"]["video_id"].startswith("abc123")


def test_creator_verse_perspectives_path_variant() -> None:
    with TestClient(app) as client:
        _ingest_sample_transcript(client, variant="b")

        response = client.get("/creators/verses/John.3.5", params={"limit_quotes": 1})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["osis"] == "John.3.5"
        assert payload["creators"], "Expected creator entries"
        creator = payload["creators"][0]
        assert len(creator["quotes"]) <= 1


def test_creator_verse_perspectives_empty_result() -> None:
    with TestClient(app) as client:
        response = client.get("/creators/verses", params={"osis": "Genesis.1.1"})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["osis"] == "Genesis.1.1"
        assert payload["total_creators"] == 0
        assert payload["creators"] == []
