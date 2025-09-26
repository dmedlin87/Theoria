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


def _ingest_sample_transcript(client: TestClient) -> str:
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
    response = client.post(
        "/ingest/transcript",
        files={"transcript": ("teaching.vtt", SAMPLE_VTT, "text/vtt")},
        data={"frontmatter": json.dumps(frontmatter)},
    )
    assert response.status_code == 200, response.text
    return response.json()["document_id"]


def test_creator_profile_endpoints_surface_quotes() -> None:
    with TestClient(app) as client:
        _ingest_sample_transcript(client)

        search = client.get("/creators/search", params={"query": "Wes"})
        assert search.status_code == 200, search.text
        payload = search.json()
        assert payload["results"]
        creator_id = payload["results"][0]["id"]

        profile = client.get(
            f"/creators/{creator_id}/topics",
            params={"topic": "Baptism", "limit": 3},
        )
        assert profile.status_code == 200, profile.text
        data = profile.json()
        assert data["creator_name"] == "Wes Huff"
        assert data["topic"].lower() == "baptism"
        assert data["stance"] == "for"
        assert data["total_claims"] >= 1
        assert data["quotes"], "Expected at least one supporting quote"
        assert "abc123" in data["quotes"][0]["source_ref"]

        transcript = client.get(
            "/transcripts/search",
            params={"osis": "John.3.5"},
        )
        assert transcript.status_code == 200, transcript.text
        t_payload = transcript.json()
        assert t_payload["segments"], "Expected transcript segments for OSIS query"
        first_segment = t_payload["segments"][0]
        assert first_segment["primary_osis"] == "John.3.5"
        assert "abc123" in (first_segment["source_ref"] or "")
