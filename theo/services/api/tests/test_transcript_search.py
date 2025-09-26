from __future__ import annotations

import json

from fastapi.testclient import TestClient

from theo.services.api.app.main import app


SAMPLE_VTT = """WEBVTT

00:00.000 --> 00:04.000
Speaker 1: We read the prologue from John 1:1-3 and ponder its light.

00:04.000 --> 00:08.000
These verses echo the creation of Genesis 1:1-2 and guide our prayers.
"""


def test_transcript_search_filters_by_osis_ranges() -> None:
    with TestClient(app) as client:
        ingest_response = client.post(
            "/ingest/transcript",
            files={"transcript": ("sermon.vtt", SAMPLE_VTT, "text/vtt")},
            data={"frontmatter": json.dumps({"title": "Creation Sermon"})},
        )
        assert ingest_response.status_code == 200, ingest_response.text

        search_response = client.get(
            "/transcripts/search",
            params={"osis": "John.1.1-1.5"},
        )
        assert search_response.status_code == 200, search_response.text

        payload = search_response.json()
        assert payload["total"] > 0
        assert payload["segments"], "Expected at least one segment to match the OSIS range"
