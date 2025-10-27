from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from theo.adapters.persistence import models
from theo.application.facades.database import get_session
from theo.infrastructure.api.app.main import app


def _override_session_factory(engine):
    factory = sessionmaker(bind=engine)

    def _override():
        with factory() as session:
            yield session

    return factory, _override


def test_dashboard_summary_returns_counts_and_activity(api_engine) -> None:
    session_factory, override = _override_session_factory(api_engine)
    app.dependency_overrides[get_session] = override

    try:
        now = datetime.now(UTC)
        with session_factory() as session:
            _seed_dashboard_records(session, now)

        with TestClient(app) as client:
            response = client.get("/dashboard")

        assert response.status_code == 200
        payload = response.json()

        assert payload["user"]["name"] == "test"
        metric_values = {metric["id"]: metric for metric in payload["metrics"]}
        assert metric_values["documents"]["value"] == 2
        assert metric_values["notes"]["value"] == 1
        assert metric_values["discoveries"]["value"] == 1
        assert metric_values["notebooks"]["value"] == 1

        assert len(payload["quick_actions"]) >= 4
        activity_entries = payload["activity"]
        activity_types = {entry["type"] for entry in activity_entries}
        assert {"document_ingested", "note_created", "discovery_published", "notebook_updated"}.issubset(activity_types)

        occurred_at_values = [datetime.fromisoformat(entry["occurred_at"]) for entry in activity_entries]
        assert occurred_at_values == sorted(occurred_at_values, reverse=True)
        assert [entry["id"] for entry in activity_entries[:4]] == [
            "document-doc-current",
            "note-note-1",
            "discovery-1",
            "notebook-nb-1",
        ]

        deltas = {metric_id: metric["delta_percentage"] for metric_id, metric in metric_values.items()}
        assert deltas["notes"] == 100.0
        assert deltas["discoveries"] == 100.0
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_dashboard_handles_empty_dataset(api_engine) -> None:
    session_factory, override = _override_session_factory(api_engine)
    app.dependency_overrides[get_session] = override

    try:
        with TestClient(app) as client:
            response = client.get("/dashboard")

        assert response.status_code == 200
        payload = response.json()
        assert payload["metrics"]
        assert all(metric["value"] == 0 for metric in payload["metrics"])
        assert payload["activity"] == []
    finally:
        app.dependency_overrides.pop(get_session, None)


def _seed_dashboard_records(session: Session, now: datetime) -> None:
    one_day_ago = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)
    three_days_ago = now - timedelta(days=3)
    four_days_ago = now - timedelta(days=4)
    previous_week = now - timedelta(days=10)

    documents = [
        models.Document(
            id="doc-current",
            title="Recent sermon",
            created_at=one_day_ago,
            updated_at=one_day_ago,
            collection="Sermons",
        ),
        models.Document(
            id="doc-previous",
            title="Earlier commentary",
            created_at=previous_week,
            updated_at=previous_week,
            collection="Commentary",
        ),
    ]

    note = models.ResearchNote(
        id="note-1",
        osis="John.3.16",
        title="Love of God",
        body="Observation",
        created_at=two_days_ago,
        updated_at=two_days_ago,
    )

    discovery = models.Discovery(
        id=1,
        user_id="test-user",
        discovery_type="theme",
        title="Pauline emphasis",
        description="New cross-reference surfaced",
        confidence=0.7,
        relevance_score=0.8,
        created_at=three_days_ago,
    )

    notebook = models.Notebook(
        id="nb-1",
        title="Lent study",
        description="Shared reflections",
        created_by="test",
        created_at=previous_week,
        updated_at=four_days_ago,
    )

    session.add_all(documents + [note, discovery, notebook])
    session.commit()
