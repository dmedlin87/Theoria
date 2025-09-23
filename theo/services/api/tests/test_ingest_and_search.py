"""Integration tests covering ingest -> search -> verse aggregator."""

from __future__ import annotations

from fastapi.testclient import TestClient

from theo.services.api.app.main import app


def _ingest_markdown(client: TestClient) -> str:
    content = """---
title: "Test Sermon"
authors:
  - "Jane Doe"
collection: "Gospels"
---

In the beginning was the Word (John 1:1-5), and the Word was with God.
Later we reflect on Genesis 1:1 in passing.
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
        document_id = _ingest_markdown(client)

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
        mentions = verse_response.json()["mentions"]
        assert mentions, "Expected verse mentions"

        document_response = client.get(f"/documents/{document_id}")
        assert document_response.status_code == 200
        document_payload = document_response.json()
        assert document_payload["id"] == document_id
        assert document_payload["passages"], "Document should contain passages"
