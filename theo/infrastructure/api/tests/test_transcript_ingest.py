"""API tests for transcript ingestion endpoint."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from theo.infrastructure.api.app.main import app

SAMPLE_VTT = """WEBVTT

00:00.000 --> 00:04.000
Speaker 1: In the beginning God created the heavens and the earth.

00:04.000 --> 00:08.000
This reflects on John 1:1-5 alongside Genesis 1:1.
"""

SAMPLE_VTT_WITH_AUDIO = """WEBVTT

00:00.000 --> 00:04.000
Speaker 1: Faith comes by hearing, drawing from Romans 10:17.

00:04.000 --> 00:08.000
We meditate on Psalm 23:1 while listening to this reflection.
"""


def test_transcript_ingest_without_audio() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/ingest/transcript",
            files={"transcript": ("sermon.vtt", SAMPLE_VTT, "text/vtt")},
            data={
                "frontmatter": json.dumps(
                    {
                        "title": "Creation Sermon Transcript",
                        "collection": "Genesis",
                        "osis_refs": ["Gen.1.1", "John.1.1-5"],
                    }
                )
            },
        )
        assert response.status_code == 200, response.text
        document_id = response.json()["document_id"]

        document = client.get(f"/documents/{document_id}").json()
        assert document["title"] == "Creation Sermon Transcript"
        assert document["source_type"] == "transcript"
        assert document["collection"] == "Genesis"
        assert document["passages"], "Expected passages to be generated"

        first_passage = document["passages"][0]
        assert first_passage["t_start"] == 0.0
        assert first_passage["t_end"] is not None
        assert first_passage["meta"]["parser"] == "transcript"
        assert first_passage["meta"]["chunker_version"] == "0.3.0"
        assert "Speaker 1" in first_passage["meta"].get("speakers", [])

        storage_path = Path(document["storage_path"])
        assert (storage_path / "sermon.vtt").exists()


def test_transcript_ingest_with_audio_upload() -> None:
    with TestClient(app) as client:
        audio_bytes = b"ID3\x04\x00\x00fake-audio"
        response = client.post(
            "/ingest/transcript",
            files={
                "transcript": ("sermon_audio.vtt", SAMPLE_VTT_WITH_AUDIO, "text/vtt"),
                "audio": ("sermon.mp3", audio_bytes, "audio/mpeg"),
            },
            data={
                "frontmatter": json.dumps(
                    {
                        "title": "Creation Sermon Audio",
                        "duration_seconds": 95,
                    }
                )
            },
        )
        assert response.status_code == 200, response.text
        document_id = response.json()["document_id"]

        document = client.get(f"/documents/{document_id}").json()
        assert document["title"] == "Creation Sermon Audio"
        assert document["duration_seconds"] == 95
        assert document["passages"], "Passages should exist for transcript ingestion"

        storage_path = Path(document["storage_path"])
        assert (storage_path / "sermon_audio.vtt").exists()
        assert (storage_path / "sermon.mp3").exists()

        passage_times = {passage["t_start"] for passage in document["passages"]}
        assert 0.0 in passage_times
