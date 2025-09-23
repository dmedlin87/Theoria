"""Integration tests covering ingest -> search -> verse aggregator."""

from __future__ import annotations

from pathlib import Path


from fastapi.testclient import TestClient

from theo.services.api.app.main import app


def _ingest_markdown(client: TestClient, *, suffix: str = "") -> str:
    content = f"""---
title: "Test Sermon"
authors:
  - "Jane Doe"
collection: "Gospels"
---

In the beginning was the Word (John 1:1-5), and the Word was with God.
Later we reflect on Genesis 1:1 in passing.
{suffix}
"""
    response = client.post(
        "/ingest/file",
        files={"file": ("sermon.md", content, "text/markdown")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload["document_id"]


def test_ingest_and_search_roundtrip() -> None:
    with TestClient(app) as client:
        document_id = _ingest_markdown(client, suffix="Additional reflection on John 3:16.")

        search_response = client.get("/search", params={"q": "Word"})
        assert search_response.status_code == 200
        results = search_response.json()["results"]
        assert results, "Expected at least one search result"
        assert any(result["document_id"] == document_id for result in results)

        osis_response = client.get("/search", params={"osis": "John.1.1-5"})
        assert osis_response.status_code == 200
        osis_results = osis_response.json()["results"]
        assert osis_results, "Expected OSIS search results"
        assert all("John.1.1" in result["osis_ref"] or result["osis_ref"] == "John.1.1-5" for result in osis_results if result["osis_ref"])

        verse_response = client.get("/verses/John.1.1/mentions")
        assert verse_response.status_code == 200
        verse_payload = verse_response.json()
        mentions = verse_payload["mentions"]
        assert mentions, "Expected verse mentions"
        assert verse_payload["total"] == len(mentions)

        document_response = client.get(f"/documents/{document_id}")
        assert document_response.status_code == 200
        document_payload = document_response.json()
        assert document_payload["id"] == document_id
        assert document_payload["passages"], "Document should contain passages"
        first_passage = document_payload["passages"][0]
        assert first_passage["meta"]["chunker_version"] == "0.3.0"
        assert first_passage["meta"]["parser"] == "plain_text"



def test_document_listing_and_paginated_passages() -> None:
    with TestClient(app) as client:
        doc_id = _ingest_markdown(client, suffix="Unique content about Psalms 23:1.")

        list_response = client.get("/documents", params={"limit": 5})
        assert list_response.status_code == 200
        listing = list_response.json()
        assert any(item["id"] == doc_id for item in listing["items"])
        assert listing["total"] >= 1

        passages_response = client.get(f"/documents/{doc_id}/passages", params={"limit": 1})
        assert passages_response.status_code == 200
        passages_payload = passages_response.json()
        assert passages_payload["document_id"] == doc_id
        assert passages_payload["passages"], "Expected at least one passage"
        assert passages_payload["total"] >= len(passages_payload["passages"])


def test_verse_mentions_filters() -> None:
    with TestClient(app) as client:
        doc_id = _ingest_markdown(
            client,
            suffix="""

This paragraph cites Romans 8:1 as well.
""",
        )

        mentions_all = client.get("/verses/John.1.1/mentions").json()
        assert mentions_all["total"] >= 1

        mentions_filtered = client.get(
            "/verses/John.1.1/mentions",
            params={"collection": "Nonexistent"},
        ).json()
        assert mentions_filtered["total"] == 0

        mentions_collection = client.get(
            "/verses/John.1.1/mentions",
            params={"collection": "Gospels"},
        ).json()
        assert mentions_collection["total"] == mentions_all["total"]

def test_pdf_ingestion_includes_page_numbers() -> None:
    with TestClient(app) as client:
        pdf_path = Path("fixtures/pdf/sample_article.pdf")
        with pdf_path.open("rb") as handle:
            response = client.post(
                "/ingest/file",
                files={"file": (pdf_path.name, handle, "application/pdf")},
            )
        assert response.status_code == 200
        document_id = response.json()["document_id"]

        doc_response = client.get(f"/documents/{document_id}")
        assert doc_response.status_code == 200
        payload = doc_response.json()
        assert payload["source_type"] == "pdf"
        assert any(passage["page_no"] == 1 for passage in payload["passages"])

        verse_mentions = client.get("/verses/John.1.1/mentions").json()
        assert verse_mentions["total"] >= 1


def test_youtube_url_ingestion_uses_fixture_transcript() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/ingest/url",
            json={"url": "https://www.youtube.com/watch?v=sample_video"},
        )
        assert response.status_code == 200, response.text
        document_id = response.json()["document_id"]

        document = client.get(f"/documents/{document_id}").json()
        assert document["source_type"] == "youtube"
        assert document["video_id"] == "sample_video"
        assert document["channel"] == "Theo Channel"
        assert any(passage["t_start"] is not None for passage in document["passages"])

        search = client.get("/search", params={"osis": "John.1.1-5"}).json()
        assert any(result["document_id"] == document_id for result in search["results"])

