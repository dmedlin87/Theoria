from __future__ import annotations

import json
from types import SimpleNamespace
from typing import cast

from sqlalchemy.orm import Session

import pytest
from fastapi.testclient import TestClient

from theo.services.api.app.ingest.parsers import TranscriptSegment
from theo.services.api.app.main import app
from theo.services.api.app.core import settings as settings_module

SAMPLE_VTT = """WEBVTT

00:00.000 --> 00:06.000
Speaker 1: Baptism in John 3:5 points to the Spirit's work.

00:06.000 --> 00:12.000
We also draw from Matthew 28:19 to discuss discipleship.
"""


def _ingest_sample_transcript(client: TestClient, *, salt: str | None = None) -> str:
    transcript_body = SAMPLE_VTT
    if salt:
        transcript_body = SAMPLE_VTT.replace("Baptism", f"Baptism {salt}")

    frontmatter = {
        "title": "Baptism Teaching" if not salt else f"Baptism Teaching {salt}",
        "collection": "teachings",
        "creator": "Wes Huff",
        "channel": "Apologia",
        "creator_tags": ["apologetics", "youtube"],
        "creator_bio": "Apologist and teacher.",
        "video_id": "abc123" if not salt else f"abc123-{salt}",
        "source_url": "https://youtu.be/abc123"
        if not salt
        else f"https://youtu.be/abc123?{salt}",
        "published_at": "2024-05-12T00:00:00Z",
        "duration_seconds": 120,
        "topics": ["Baptism", "Grace"],
        "creator_stances": {"baptism": "for"},
        "creator_confidence": 0.75,
    }
    response = client.post(
        "/ingest/transcript",
        files={"transcript": ("teaching.vtt", transcript_body, "text/vtt")},
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


def test_creator_verse_perspectives_endpoint() -> None:
    with TestClient(app) as client:
        _ingest_sample_transcript(client, salt="perspectives")

        response = client.get(
            "/creators/verses",
            params={"osis": "John.3.5", "limit_creators": 5, "limit_quotes": 2},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["osis"] == "John.3.5"
        assert payload["total_creators"] >= 1
        assert payload["creators"], "Expected at least one creator perspective"
        first_creator = payload["creators"][0]
        assert first_creator["quotes"], "Expected at least one quote for the creator"
        meta = payload.get("meta")
        assert meta and meta["range"] == "John.3.5"
        assert meta.get("generated_at")


def test_creator_verse_perspectives_respects_feature_flag() -> None:
    with TestClient(app) as client:
        _ingest_sample_transcript(client, salt="flag")

        settings = settings_module.get_settings()
        original = settings.creator_verse_perspectives_enabled
        settings.creator_verse_perspectives_enabled = False
        try:
            response = client.get(
                "/creators/verses",
                params={"osis": "John.3.5"},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["creators"] == []
            assert payload["total_creators"] == 0
            assert payload.get("meta") is None
        finally:
            settings.creator_verse_perspectives_enabled = original


def test_creator_rollups_async_refresh_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(app) as client:
        settings = settings_module.get_settings()
        original_async = settings.creator_verse_rollups_async_refresh
        settings.creator_verse_rollups_async_refresh = True
        try:
            from theo.services.api.app.workers import tasks as worker_tasks

            def fake_delay(*args, **kwargs):  # pragma: no cover - invoked for side effects
                raise RuntimeError("broker unavailable")

            monkeypatch.setattr(
                worker_tasks.refresh_creator_verse_rollups,
                "delay",
                fake_delay,
                raising=True,
            )

            _ingest_sample_transcript(client, salt="async")

            response = client.get(
                "/creators/verses",
                params={"osis": "John.3.5", "limit_creators": 1, "limit_quotes": 1},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["total_creators"] >= 1
        finally:
            settings.creator_verse_rollups_async_refresh = original_async


def test_refresh_creator_rollups_helper_handles_async_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_module.get_settings()
    original_async = settings.creator_verse_rollups_async_refresh
    settings.creator_verse_rollups_async_refresh = True
    try:
        from theo.services.api.app.workers import tasks as worker_tasks
        from theo.services.api.app.ingest.pipeline import _refresh_creator_verse_rollups

        recorded: list[list[str]] = []

        def fake_delay(refs, *_, **__):
            recorded.append(list(refs))
            raise RuntimeError("broker unavailable")

        monkeypatch.setattr(
            worker_tasks.refresh_creator_verse_rollups,
            "delay",
            fake_delay,
            raising=True,
        )

        service_calls: list[list[str]] = []

        def fake_refresh_many(self, refs):
            service_calls.append(list(refs))

        monkeypatch.setattr(
            "theo.services.api.app.creators.verse_perspectives.CreatorVersePerspectiveService.refresh_many",
            fake_refresh_many,
        )

        session_stub = cast(Session, SimpleNamespace())
        segments = [
            cast(TranscriptSegment, SimpleNamespace(osis_refs=["John.3.6", "John.3.5"]))
        ]

        _refresh_creator_verse_rollups(session_stub, segments)

        assert recorded and sorted(recorded[0]) == ["John.3.5", "John.3.6"]
        assert service_calls and service_calls[0] == ["John.3.5", "John.3.6"]
    finally:
        settings.creator_verse_rollups_async_refresh = original_async
