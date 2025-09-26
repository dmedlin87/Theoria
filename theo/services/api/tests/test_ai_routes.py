"""Tests for AI routes and workflows."""

from __future__ import annotations

from click.testing import CliRunner
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from theo.services.api.app.core.database import get_engine
from theo.services.api.app.db.models import Document, Passage
from theo.services.api.app.main import app
from theo.services.cli.batch_intel import main as batch_intel_main


def _seed_corpus() -> None:
    engine = get_engine()
    with Session(engine) as session:
        if session.get(Document, "doc-1"):
            return
        doc = Document(
            id="doc-1",
            title="Sample Sermon",
            source_type="markdown",
            collection="Gospels",
            bib_json={"primary_topic": "Pauline eschatology"},
        )
        passage = Passage(
            id="passage-1",
            document_id="doc-1",
            text="In John 1:1 the Word is proclaimed.",
            osis_ref="John.1.1",
            page_no=1,
        )
        doc.passages.append(passage)
        transcript = Document(
            id="doc-2",
            title="Q&A Transcript",
            source_type="audio",
            collection="Gospels",
        )
        transcript_passage = Passage(
            id="passage-2",
            document_id="doc-2",
            text="Question: How is the Logos understood?",
            osis_ref="John.1.1",
            t_start=10.0,
            t_end=25.0,
            meta={"speaker": "Student"},
        )
        transcript.passages.append(transcript_passage)
        session.add_all([doc, transcript])
        session.commit()


def test_verse_copilot_returns_citations() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        client.post(
            "/ai/llm", json={"name": "echo", "provider": "echo", "model": "echo"}
        )
        response = client.post(
            "/ai/verse",
            json={"osis": "John.1.1", "question": "What is said?", "model": "echo"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["answer"]["citations"], payload
        for citation in payload["answer"]["citations"]:
            assert citation["osis"] == "John.1.1"


def test_sermon_prep_export_markdown() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        response = client.post(
            "/ai/sermon-prep/export",
            params={"format": "markdown"},
            json={"topic": "Logos", "osis": "John.1.1"},
        )
        assert response.status_code == 200
        body = response.text
        assert body.startswith("---\nexport_id:")
        assert "Sermon Prep" in body


def test_transcript_export_csv() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        response = client.post(
            "/ai/transcript/export",
            json={"document_id": "doc-2", "format": "csv"},
        )
        assert response.status_code == 200
        text = response.text
        assert "export_id=transcript-doc-2" in text
        assert "Student" in text


def test_topic_digest_generation() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        response = client.post("/ai/digest", params={"hours": 24})
        assert response.status_code == 200
        payload = response.json()
        assert payload["topics"]
        assert payload["topics"][0]["topic"] == "Pauline eschatology"

        digest_document_response = client.get("/documents/digest")
        assert digest_document_response.status_code == 200
        digest_document = digest_document_response.json()
        assert digest_document["source_type"] == "digest"
        assert digest_document["topics"] == ["Pauline eschatology"]
        clusters = digest_document["meta"]["clusters"]
        assert clusters
        assert "doc-1" in clusters[0]["document_ids"]


def test_batch_intel_cli(tmp_path) -> None:
    _seed_corpus()
    runner = CliRunner()
    result = runner.invoke(batch_intel_main, ["--hours", "48", "--dry-run"])
    assert result.exit_code == 0
    assert "Summarising" in result.output
