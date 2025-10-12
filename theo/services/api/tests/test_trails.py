from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from theo.application.facades.database import get_engine
from theo.services.api.app.db.models import AgentTrail, Document, Passage
from theo.services.api.app.main import app


def _seed_corpus() -> None:
    engine = get_engine()
    with Session(engine) as session:
        if session.get(Document, "trail-doc-1"):
            return
        doc = Document(
            id="trail-doc-1",
            title="Trail Sermon",
            source_type="markdown",
            collection="Gospels",
        )
        passage = Passage(
            id="trail-passage-1",
            document_id="trail-doc-1",
            text="In the beginning was the Word.",
            osis_ref="John.1.1",
            page_no=1,
        )
        doc.passages.append(passage)
        session.add(doc)
        session.commit()


def test_trail_persistence_and_replay() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        client.post(
            "/ai/llm", json={"name": "echo", "provider": "echo", "model": "echo"}
        )
        response = client.post(
            "/ai/verse",
            json={"osis": "John.1.1", "question": "What is declared?", "model": "echo"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["answer"]["citations"], payload

        engine = get_engine()
        with Session(engine) as session:
            trail = (
                session.query(AgentTrail).order_by(AgentTrail.created_at.desc()).first()
            )
            assert trail is not None
            trail_id = trail.id
            assert trail.workflow == "verse_copilot"
            assert trail.plan_md is not None

        trail_response = client.get(f"/trails/{trail_id}")
        assert trail_response.status_code == 200
        trail_payload = trail_response.json()
        assert trail_payload["status"] == "completed"
        assert trail_payload["steps"], trail_payload
        assert any(step["tool"] == "llm.generate" for step in trail_payload["steps"])
        assert trail_payload["sources"], trail_payload

        replay_response = client.post(f"/trails/{trail_id}/replay")
        assert replay_response.status_code == 200
        replay_payload = replay_response.json()
        assert replay_payload["trail_id"] == trail_id
        assert replay_payload["replay_output"]["answer"]["summary"]
        assert replay_payload["diff"]["summary_changed"] in {True, False}
        assert "added_citations" in replay_payload["diff"]


def test_sermon_prep_trail_replay_diff_metadata() -> None:
    _seed_corpus()
    with TestClient(app) as client:
        client.post(
            "/ai/llm", json={"name": "echo", "provider": "echo", "model": "echo"}
        )
        response = client.post(
            "/ai/sermon-prep",
            json={
                "topic": "Abiding Hope",
                "osis": "John.1.1",
                "model": "echo",
                "recorder_metadata": {"user_id": "minister-42"},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["outline"], payload

        engine = get_engine()
        with Session(engine) as session:
            trail = (
                session.query(AgentTrail)
                .filter(AgentTrail.workflow == "sermon_prep")
                .order_by(AgentTrail.created_at.desc())
                .first()
            )
            assert trail is not None
            trail_id = trail.id
            assert trail.user_id == "minister-42"

        trail_response = client.get(f"/trails/{trail_id}")
        assert trail_response.status_code == 200
        trail_payload = trail_response.json()
        assert trail_payload["workflow"] == "sermon_prep"
        assert trail_payload["status"] == "completed"
        assert any(step["tool"] == "hybrid_search" for step in trail_payload["steps"])

        replay_response = client.post(f"/trails/{trail_id}/replay")
        assert replay_response.status_code == 200
        replay_payload = replay_response.json()
        assert replay_payload["trail_id"] == trail_id
        assert replay_payload["replay_output"]["outline"], replay_payload
        assert replay_payload["replay_output"]["answer"]["citations"], replay_payload
        diff = replay_payload["diff"]
        assert diff["summary_changed"] in {True, False}
        assert "added_citations" in diff
        assert "removed_citations" in diff
        assert isinstance(diff["added_citations"], list)
        assert isinstance(diff["removed_citations"], list)
