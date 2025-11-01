"""Analytics telemetry integration tests covering event and dashboard flows."""

from __future__ import annotations

import importlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Iterable

import pytest
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from theo.adapters.persistence import Base
from theo.adapters.persistence.models import (
    Discovery,
    Document,
    FeedbackEvent,
    FeedbackEventAction,
    Notebook,
    ResearchNote,
)


def _import_module(preferred: str, fallback: str):
    """Import ``preferred`` module, falling back to ``fallback`` when missing."""

    try:
        return importlib.import_module(preferred)
    except ModuleNotFoundError:  # pragma: no cover - compatibility for legacy layouts
        return importlib.import_module(fallback)


telemetry_module = _import_module(
    "theo.services.api.app.analytics.telemetry",
    "theo.infrastructure.api.app.analytics.telemetry",
)
topics_module = _import_module(
    "theo.services.api.app.analytics.topics",
    "theo.infrastructure.api.app.analytics.topics",
)
dashboard_module = _import_module(
    "theo.services.api.app.routes.dashboard",
    "theo.infrastructure.api.app.routes.dashboard",
)
analytics_models = _import_module(
    "theo.services.api.app.models.analytics",
    "theo.infrastructure.api.app.models.analytics",
)

TelemetryBatch = getattr(analytics_models, "TelemetryBatch")
TelemetryEvent = getattr(analytics_models, "TelemetryEvent")
FeedbackEventPayload = getattr(analytics_models, "FeedbackEventPayload")


@pytest.fixture()
def session() -> Iterable[Session]:
    """Provide a fresh in-memory database session for each test."""

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with SessionLocal() as session_obj:
            yield session_obj
    finally:
        engine.dispose()


def test_record_client_telemetry_emits_log_entries(caplog: pytest.LogCaptureFixture) -> None:
    batch = TelemetryBatch(
        page="research-dashboard",
        events=[
            TelemetryEvent(
                event="copilot.latency",
                duration_ms=123.4,
                workflow="rag-chat",
                metadata={"result_count": 5, "success": True},
            ),
            TelemetryEvent(event="copilot.render", duration_ms=45.6, metadata=None),
        ],
    )

    caplog.set_level(logging.INFO, telemetry_module.LOGGER.name)

    telemetry_module.record_client_telemetry(batch)

    records = [record for record in caplog.records if record.name == telemetry_module.LOGGER.name]
    assert len(records) == 2
    assert all(record.getMessage() == "client.telemetry" for record in records)

    first, second = records
    assert first.page == "research-dashboard"
    assert first.event == "copilot.latency"
    assert first.duration_ms == pytest.approx(123.4)
    assert first.workflow == "rag-chat"
    assert first.metadata == {"result_count": 5, "success": True}

    assert second.page == "research-dashboard"
    assert second.event == "copilot.render"
    assert second.duration_ms == pytest.approx(45.6)
    assert second.workflow is None
    assert second.metadata == {}


def test_record_feedback_event_persists_and_logs(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, telemetry_module.LOGGER.name)

    telemetry_module.record_feedback_event(
        session,
        action=FeedbackEventAction.CLICK,
        user_id="user-7",
        chat_session_id="chat-42",
        query="Explain Psalm 23",
        document_id="doc-1",
        passage_id="passage-9",
        rank=2,
        score=0.66,
        confidence=0.73,
    )

    stored = session.query(FeedbackEvent).one()
    assert stored.action is FeedbackEventAction.CLICK
    assert stored.user_id == "user-7"
    assert stored.chat_session_id == "chat-42"
    assert stored.query == "Explain Psalm 23"
    assert stored.document_id == "doc-1"
    assert stored.passage_id == "passage-9"
    assert stored.rank == 2
    assert stored.score == pytest.approx(0.66)
    assert stored.confidence == pytest.approx(0.73)

    log_record = next(
        record
        for record in caplog.records
        if record.name == telemetry_module.LOGGER.name and record.getMessage() == "client.feedback_event"
    )
    assert log_record.action == FeedbackEventAction.CLICK.value
    assert log_record.user_id == "user-7"
    assert log_record.document_id == "doc-1"


def test_record_feedback_from_payload_delegates_to_persistence(session: Session) -> None:
    payload = FeedbackEventPayload(
        action="like",
        user_id="user-9",
        document_id="doc-77",
        passage_id="passage-3",
        rank=0,
        score=0.98,
        confidence=0.81,
    )

    telemetry_module.record_feedback_from_payload(session, payload)

    stored = session.query(FeedbackEvent).one()
    assert stored.action is FeedbackEventAction.LIKE
    assert stored.document_id == "doc-77"
    assert stored.rank == 0
    assert stored.score == pytest.approx(0.98)


def test_generate_topic_digest_fetches_missing_topics(session: Session) -> None:
    now = datetime.now(UTC)

    existing = Document(
        id="doc-existing",
        title="Existing Topic",
        doi="10.1111/existing",
        topics=["Already Tagged"],
        created_at=now,
        updated_at=now,
    )
    missing = Document(
        id="doc-missing",
        title="Needs Topics",
        doi="10.2222/missing",
        created_at=now,
        updated_at=now,
    )
    session.add_all([existing, missing])
    session.flush()

    class FakeOpenAlex:
        def __init__(self) -> None:
            self.calls: list[tuple[str | None, str | None]] = []

        def fetch_topics(self, doi: str | None, title: str | None) -> list[str]:
            self.calls.append((doi, title))
            return ["Theology", "Biblical Studies", "Theology"]

    fake_client = FakeOpenAlex()

    digest = topics_module.generate_topic_digest(
        session,
        since=now - timedelta(days=1),
        openalex_client=fake_client,
    )

    assert fake_client.calls == [("10.2222/missing", "Needs Topics")]

    session.refresh(missing)
    assert list(dict.fromkeys(missing.topics or [])) == [
        "Theology",
        "Biblical Studies",
    ]

    cluster_topics = {cluster.topic for cluster in digest.topics}
    assert "Theology" in cluster_topics
    assert "Biblical Studies" in cluster_topics
    assert any("doc-missing" in cluster.document_ids for cluster in digest.topics)


def test_dashboard_summary_shapes_metrics_and_activity(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_now = datetime(2024, 1, 8, 12, 0, tzinfo=UTC)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now

    monkeypatch.setattr(dashboard_module, "datetime", FrozenDateTime)

    recent_doc = Document(
        id="doc-new",
        title="Recent Document",
        created_at=fixed_now - timedelta(days=2),
        updated_at=fixed_now - timedelta(days=2),
    )
    prior_doc = Document(
        id="doc-old",
        title="Prior Document",
        created_at=fixed_now - timedelta(days=8),
        updated_at=fixed_now - timedelta(days=8),
    )
    recent_note = ResearchNote(
        id="note-new",
        osis="Gen.1.1",
        body="In the beginning",
        created_at=fixed_now - timedelta(days=1),
        updated_at=fixed_now - timedelta(days=1),
    )
    prior_note = ResearchNote(
        id="note-old",
        osis="Gen.1.2",
        body="And the earth was without form, and void; and darkness was upon the face of the deep",
        created_at=fixed_now - timedelta(days=10),
        updated_at=fixed_now - timedelta(days=10),
    )
    recent_discovery = Discovery(
        user_id="user-1",
        discovery_type="insight",
        title="Fresh Insight",
        description="New evidence surfaced",
        created_at=fixed_now - timedelta(days=1),
    )
    prior_discovery = Discovery(
        user_id="user-1",
        discovery_type="insight",
        title="Older Insight",
        description="From last week",
        created_at=fixed_now - timedelta(days=8),
    )
    notebook = Notebook(
        id="nb-1",
        title="Theo Notebook",
        description="Notes",
        created_by="user-1",
        created_at=fixed_now - timedelta(days=2),
        updated_at=fixed_now - timedelta(days=2),
    )

    session.add_all(
        [
            recent_doc,
            prior_doc,
            recent_note,
            prior_note,
            recent_discovery,
            prior_discovery,
            notebook,
        ]
    )
    session.flush()

    scope = {"type": "http"}
    request = Request(scope)
    request.state.principal = {
        "name": "Dr. Stone",
        "plan": "pro",
        "timezone": "UTC",
        "last_login": "2024-01-06T09:30:00",
    }

    summary = dashboard_module.get_dashboard_summary(request, session=session)

    assert summary.user.name == "Dr. Stone"
    assert summary.user.plan == "pro"
    assert summary.user.last_login == datetime(2024, 1, 6, 9, 30, tzinfo=UTC)

    metrics = {metric.id: metric for metric in summary.metrics}
    assert metrics["documents"].value == pytest.approx(2.0)
    assert metrics["documents"].delta_percentage == pytest.approx(0.0)
    assert metrics["notes"].value == pytest.approx(2.0)
    assert metrics["discoveries"].value == pytest.approx(2.0)
    assert metrics["notebooks"].value == pytest.approx(1.0)
    assert metrics["notebooks"].delta_percentage == pytest.approx(100.0)

    assert len(summary.activity) == 7
    activity_ids = {item.id for item in summary.activity}
    assert f"document-{recent_doc.id}" in activity_ids
    assert f"note-{recent_note.id}" in activity_ids
    assert f"discovery-{recent_discovery.id}" in activity_ids
    assert f"notebook-{notebook.id}" in activity_ids

    assert len(summary.quick_actions) == 4
