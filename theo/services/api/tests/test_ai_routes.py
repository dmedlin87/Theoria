"""Tests for AI routes and workflows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from click.testing import CliRunner
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.services.api.app.core.database import get_engine
from theo.services.api.app.db.models import AgentTrail, Document, Passage
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
            topics=["Pauline eschatology", "Christology"],
            bib_json={"primary_topic": "Pauline eschatology"},
        )
        passage = Passage(
            id="passage-1",
            document_id="doc-1",
            text=(
                "In John 1:1 the Word is proclaimed as light that brings abiding hope; "
                "these highlights anchor faith in the Logos."
            ),
            osis_ref="John.1.1",
            page_no=1,
        )
        doc.passages.append(passage)
        transcript = Document(
            id="doc-2",
            title="Q&A Transcript",
            source_type="audio",
            collection="Gospels",
            topics=["Hope", "Logos"],
        )
        transcript_passage = Passage(
            id="passage-2",
            document_id="doc-2",
            text=(
                "Audio highlights exploring how the Logos is understood with abiding hope."
            ),
            osis_ref="John.1.1",
            t_start=10.0,
            t_end=25.0,
            meta={"speaker": "Student"},
        )
        transcript.passages.append(transcript_passage)
        session.add_all([doc, transcript])
        session.commit()


def test_verse_copilot_returns_citations_and_followups() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        client.post(
            "/ai/llm", json={"name": "echo", "provider": "echo", "model": "echo"}
        )
        response = client.post(
            "/ai/verse",
            json={
                "osis": "John.1.1",
                "question": "What is said?",
                "model": "echo",
                "recorder_metadata": {"user_id": "user-123", "source": "pytest"},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["answer"]["citations"], payload
        for citation in payload["answer"]["citations"]:
            assert citation["osis"] == "John.1.1"
            assert citation["snippet"], citation
        assert payload["follow_ups"], payload
        with Session(get_engine()) as session:
            trail = (
                session.execute(
                    select(AgentTrail)
                    .where(
                        AgentTrail.workflow == "verse_copilot",
                        AgentTrail.status == "completed",
                    )
                    .order_by(AgentTrail.started_at.desc())
                )
                .scalars()
                .first()
            )
            assert trail is not None
            assert trail.user_id == "user-123"


def test_verse_copilot_guardrails_when_no_citations() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        response = client.post(
            "/ai/verse",
            json={"osis": "Gen.99.1", "question": "Missing?"},
        )
        assert response.status_code == 422


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


def test_sermon_prep_outline_returns_key_points_and_trail_user() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        response = client.post(
            "/ai/sermon-prep",
            json={
                "topic": "Logos",
                "osis": "John.1.1",
                "recorder_metadata": {"user_id": "preacher-7"},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["answer"]["citations"], payload
        assert payload["key_points"], payload
        with Session(get_engine()) as session:
            trail = (
                session.execute(
                    select(AgentTrail)
                    .where(
                        AgentTrail.workflow == "sermon_prep",
                        AgentTrail.status == "completed",
                    )
                    .order_by(AgentTrail.started_at.desc())
                )
                .scalars()
                .first()
            )
            assert trail is not None
            assert trail.user_id == "preacher-7"


def test_sermon_prep_guardrails_when_no_results() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        response = client.post(
            "/ai/sermon-prep",
            json={"topic": "Unknown", "osis": "Rev.99.1"},
        )
        assert response.status_code == 422


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


def test_comparative_analysis_returns_citations_and_comparisons() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        client.post("/ai/llm", json={"name": "echo", "provider": "echo", "model": "echo"})
        response = client.post(
            "/ai/comparative",
            json={
                "osis": "John.1.1",
                "participants": ["Origen", "Augustine"],
                "model": "echo",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        citations = payload["answer"]["citations"]
        assert citations, payload
        for citation in citations:
            assert citation["osis"] == "John.1.1"
            assert citation["snippet"]
            assert citation["passage_id"]
        assert payload["comparisons"], payload
        assert any("Sample Sermon" in comparison for comparison in payload["comparisons"])


def test_multimedia_digest_highlights_audio_sources() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        client.post("/ai/llm", json={"name": "echo", "provider": "echo", "model": "echo"})
        response = client.post(
            "/ai/multimedia",
            json={"collection": "Gospels", "model": "echo"},
        )
        assert response.status_code == 200
        payload = response.json()
        citations = payload["answer"]["citations"]
        assert citations, payload
        for citation in citations:
            assert citation["document_id"] == "doc-2"
            assert citation["snippet"]
            assert citation["anchor"].startswith("t=")
        assert payload["highlights"], payload
        assert any("highlights" in highlight.lower() for highlight in payload["highlights"])


def test_devotional_flow_returns_reflection_and_prayer() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        client.post("/ai/llm", json={"name": "echo", "provider": "echo", "model": "echo"})
        response = client.post(
            "/ai/devotional",
            json={"osis": "John.1.1", "focus": "Word", "model": "echo"},
        )
        assert response.status_code == 200
        payload = response.json()
        citations = payload["answer"]["citations"]
        assert citations, payload
        for citation in citations:
            assert citation["osis"] == "John.1.1"
            assert citation["snippet"]
        assert "Reflect on" in payload["reflection"]
        assert payload["prayer"].startswith("Spirit")


def test_collaboration_reconciliation_includes_synthesized_view() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        client.post("/ai/llm", json={"name": "echo", "provider": "echo", "model": "echo"})
        response = client.post(
            "/ai/collaboration",
            json={
                "thread": "forum-thread-1",
                "osis": "John.1.1",
                "viewpoints": ["Logos", "Creation"],
                "model": "echo",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        citations = payload["answer"]["citations"]
        assert citations, payload
        for citation in citations:
            assert citation["osis"] == "John.1.1"
            assert citation["snippet"]
        assert "John.1.1" in payload["synthesized_view"]


def test_corpus_curation_report_persists_summaries() -> None:
    _seed_corpus()
    since = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    with TestClient(app) as client:
        response = client.post("/ai/curation", json={"since": since})
        assert response.status_code == 200
        payload = response.json()
        assert payload["documents_processed"] >= 1
        assert any(summary.startswith("Sample Sermon") for summary in payload["summaries"])
        assert payload["since"].startswith(since[:10])


def test_topic_digest_generation() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        response = client.post("/ai/digest", params={"hours": 24})
        assert response.status_code == 200
        payload = response.json()
        assert payload["topics"]
        topic_labels = {topic["topic"] for topic in payload["topics"]}
        assert "Pauline eschatology" in topic_labels

        digest_document_response = client.get("/documents/digest")
        assert digest_document_response.status_code == 200
        digest_document = digest_document_response.json()
        assert digest_document["source_type"] == "digest"
        assert "Pauline eschatology" in digest_document["topics"]
        clusters = digest_document["meta"]["clusters"]
        assert clusters
        assert "doc-1" in clusters[0]["document_ids"]


def test_batch_intel_cli(tmp_path) -> None:
    _seed_corpus()
    runner = CliRunner()
    result = runner.invoke(batch_intel_main, ["--hours", "48", "--dry-run"])
    assert result.exit_code == 0
    assert "Summarising" in result.output
