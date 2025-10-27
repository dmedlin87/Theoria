"""Integration tests covering ingest -> search -> verse aggregator."""

from __future__ import annotations

import json
import threading
import wave
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from ipaddress import ip_address
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape

from fastapi.testclient import TestClient

from theo.infrastructure.api.app.main import app


def _start_static_server(
    directory: Path,
) -> tuple[ThreadingHTTPServer, threading.Thread]:
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


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


def _build_docx(paragraphs: list[str]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""",
        )
        body = "".join(
            f"<w:p><w:r><w:t>{escape(paragraph)}</w:t></w:r></w:p>"
            for paragraph in paragraphs
        )
        archive.writestr(
            "word/document.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{body}</w:body>
</w:document>
""",
        )
        archive.writestr(
            "docProps/core.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Docx Sermon</dc:title>
  <dc:creator>John Wordsmith</dc:creator>
</cp:coreProperties>
""",
        )
    buffer.seek(0)
    return buffer.read()


def _build_wav(duration_seconds: float = 1.0, sample_rate: int = 8000) -> bytes:
    buffer = BytesIO()
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)
    buffer.seek(0)
    return buffer.read()


def test_ingest_and_search_roundtrip() -> None:
    with TestClient(app) as client:
        document_id = _ingest_markdown(
            client, suffix="Additional reflection on John 3:16."
        )

        search_response = client.get("/search", params={"q": "Word"})
        assert search_response.status_code == 200
        results = search_response.json()["results"]
        assert results, "Expected at least one search result"
        assert any(result["document_id"] == document_id for result in results)

        osis_response = client.get("/search", params={"osis": "John.1.1-5"})
        assert osis_response.status_code == 200
        osis_results = osis_response.json()["results"]
        assert osis_results, "Expected OSIS search results"
        assert all(
            "John.1.1" in result["osis_ref"] or result["osis_ref"] == "John.1.1-5"
            for result in osis_results
            if result["osis_ref"]
        )

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


def test_hybrid_search_combines_keyword_and_osis_filters() -> None:
    with TestClient(app) as client:
        document_id = _ingest_markdown(
            client,
            suffix="Keyword rich reflection mentioning John 1:1-5 repeatedly for emphasis.",
        )

        response = client.get(
            "/search",
            params={"q": "Keyword reflection", "osis": "John.1.1-5", "k": 5},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        results = payload["results"]
        assert results, "Expected hybrid search results"
        assert len({result["id"] for result in results}) == len(results)
        assert all(
            result["osis_ref"] and result["osis_ref"].startswith("John.1.1")
            for result in results
        )
        assert all(result["snippet"].strip() for result in results)
        assert all(
            result.get("meta", {}).get("document_title")
            for result in results
            if result.get("meta")
        )
        assert any(result["document_id"] == document_id for result in results)


def test_export_endpoints_return_bulk_payloads() -> None:
    with TestClient(app) as client:
        document_id = _ingest_markdown(
            client, suffix="Additional passage content for export testing."
        )

        search_export = client.get(
            "/export/search",
            params={"q": "Word", "k": 5, "format": "json", "include_text": "true"},
        )
        assert search_export.status_code == 200, search_export.text
        search_payload = search_export.json()
        manifest = search_payload["manifest"]
        assert manifest["totals"]["results"] >= 1
        records = search_payload["records"]
        assert records, "Expected exported search results"
        first_row = records[0]
        assert first_row["document_id"]
        assert first_row["snippet"].strip()
        assert first_row.get("text"), "Passage text should be included when requested"

        docs_export = client.get(
            "/export/documents",
            params={"collection": "Gospels", "limit": 10, "format": "json"},
        )
        assert docs_export.status_code == 200, docs_export.text
        docs_payload = docs_export.json()
        doc_manifest = docs_payload["manifest"]
        assert doc_manifest["totals"]["documents"] >= 1
        exported_records = docs_payload["records"]
        assert exported_records, "Expected exported documents"
        exported_ids = {doc["document_id"] for doc in exported_records}
        assert document_id in exported_ids
        exported_doc = next(
            doc for doc in exported_records if doc["document_id"] == document_id
        )
        assert exported_doc["passages"], "Passages should be included by default"

        docs_without_passages = client.get(
            "/export/documents",
            params={
                "collection": "Gospels",
                "include_passages": "false",
                "format": "json",
            },
        )
        assert docs_without_passages.status_code == 200
        payload_without = docs_without_passages.json()
        assert payload_without["manifest"]["totals"]["passages"] == 0
        assert all(not doc.get("passages") for doc in payload_without["records"])


def test_document_listing_and_paginated_passages() -> None:
    with TestClient(app) as client:
        doc_id = _ingest_markdown(client, suffix="Unique content about Psalms 23:1.")

        list_response = client.get("/documents", params={"limit": 5})
        assert list_response.status_code == 200
        listing = list_response.json()
        assert any(item["id"] == doc_id for item in listing["items"])
        assert listing["total"] >= 1

        passages_response = client.get(
            f"/documents/{doc_id}/passages", params={"limit": 1}
        )
        assert passages_response.status_code == 200
        passages_payload = passages_response.json()
        assert passages_payload["document_id"] == doc_id
        assert passages_payload["passages"], "Expected at least one passage"
        assert passages_payload["total"] >= len(passages_payload["passages"])


def test_verse_mentions_filters() -> None:
    with TestClient(app) as client:
        _ingest_markdown(
            client,
            suffix="""

This paragraph cites Romans 8:1 as well.
""",
        )

        mentions_all = client.get("/verses/John.1.1/mentions").json()
        assert mentions_all["total"] >= 1
        assert all(
            mention["passage"]["osis_ref"]
            and mention["passage"]["osis_ref"].startswith("John.1.1")
            for mention in mentions_all["mentions"]
        )
        assert all(
            mention["passage"].get("meta", {}).get("document_title")
            for mention in mentions_all["mentions"]
            if mention["passage"].get("meta")
        )

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


def test_html_url_ingestion_and_searchable() -> None:
    html_dir = Path("fixtures/html").resolve()
    server, thread = _start_static_server(html_dir)
    try:
        with TestClient(app) as client:
            url = f"http://127.0.0.1:{server.server_port}/sample_page.html"
            response = client.post("/ingest/url", json={"url": url})
            assert response.status_code == 200, response.text
            document_id = response.json()["document_id"]

            document = client.get(f"/documents/{document_id}").json()
            assert document["source_type"] == "web_page"
            assert document["source_url"] == "https://example.com/sample-sermon"
            assert document["title"] == "Sample HTML Sermon"
            assert any(
                "John 1:1-5" in passage["text"] for passage in document["passages"]
            )
            assert all(
                "ignore this script" not in passage["text"]
                for passage in document["passages"]
            )

            search = client.get("/search", params={"q": "reflection"}).json()
            assert any(
                result["document_id"] == document_id for result in search["results"]
            )

            osis = client.get("/search", params={"osis": "John.1.1-5"}).json()
            assert any(
                result["document_id"] == document_id for result in osis["results"]
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_url_ingest_rejects_domain_resolving_to_blocked_network() -> None:
    with TestClient(app) as client:
        with patch(
            "theo.infrastructure.api.app.ingest.pipeline._resolve_host_addresses",
            return_value=(ip_address("127.0.0.1"),),
        ) as resolver:
            response = client.post(
                "/ingest/url", json={"url": "http://blocked.example/resource"}
            )

        resolver.assert_called()
        assert response.status_code == 400
        payload = response.json()
        assert payload["detail"] == "URL target is not allowed for ingestion"


def test_docx_ingestion_uses_doc_parser() -> None:
    with TestClient(app) as client:
        payload = _build_docx(
            [
                "Docx sermons often cite John 1:1 to begin.",
                "They may also mention Genesis 1:1 for context.",
            ]
        )
        response = client.post(
            "/ingest/file",
            files={
                "file": (
                    "sermon.docx",
                    BytesIO(payload),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert response.status_code == 200, response.text
        document_id = response.json()["document_id"]

        document = client.get(f"/documents/{document_id}").json()
        assert document["source_type"] == "docx"
        assert document["title"] == "Docx Sermon"
        assert any("Genesis 1:1" in passage["text"] for passage in document["passages"])


def test_html_ingestion_extracts_title() -> None:
    with TestClient(app) as client:
        html = """<!doctype html><html><head><title>HTML Homily</title></head><body><h1>Intro</h1><p>The message references John 1:1-5 clearly.</p><p>We also note Psalm 23:1.</p></body></html>"""
        response = client.post(
            "/ingest/file",
            files={"file": ("homily.html", html, "text/html")},
        )
        assert response.status_code == 200, response.text
        document_id = response.json()["document_id"]

        document = client.get(f"/documents/{document_id}").json()
        assert document["source_type"] == "html"
        assert document["title"] == "HTML Homily"
        assert any("Psalm 23:1" in passage["text"] for passage in document["passages"])


def test_audio_ingestion_with_inline_transcript() -> None:
    with TestClient(app) as client:
        wav_bytes = _build_wav()
        frontmatter = {
            "title": "Audio Sermon",
            "transcript_segments": [
                {
                    "text": "Welcome to the reflection on John 1:1.",
                    "start": 0.0,
                    "end": 2.0,
                    "speaker": "Host",
                },
                {
                    "text": "We remember Genesis 1:1 as well.",
                    "start": 2.0,
                    "end": 4.0,
                },
            ],
        }

        response = client.post(
            "/ingest/file",
            data={"frontmatter": json.dumps(frontmatter)},
            files={"file": ("sermon.wav", BytesIO(wav_bytes), "audio/wav")},
        )
        assert response.status_code == 200, response.text
        document_id = response.json()["document_id"]

        document = client.get(f"/documents/{document_id}").json()
        assert document["source_type"] == "audio"
        assert any(passage["t_start"] is not None for passage in document["passages"])
        assert any(
            passage["meta"].get("speakers") == ["Host"]
            for passage in document["passages"]
            if passage["meta"]
        )

        mentions = client.get("/verses/John.1.1/mentions").json()
        assert any(
            item["passage"]["document_id"] == document_id
            for item in mentions["mentions"]
        )
