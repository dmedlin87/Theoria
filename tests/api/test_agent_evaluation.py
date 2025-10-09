"""Unit tests for agent evaluation metrics."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from theo.services.api.app.analytics.agent_evaluation import (
    evaluate_agent_trails,
)
from theo.services.api.app.core.database import Base
from theo.services.api.app.db.models import (
    AgentStep,
    AgentTrail,
    TrailRetrievalSnapshot,
)


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db_session = TestingSession()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _make_trail(
    *,
    workflow: str,
    status: str,
    started_at: datetime,
    plan_md: str | None,
    steps: list[AgentStep],
    snapshots: list[TrailRetrievalSnapshot],
) -> AgentTrail:
    trail = AgentTrail(
        workflow=workflow,
        status=status,
        plan_md=plan_md,
        input_payload={},
        started_at=started_at,
    )
    for step in steps:
        trail.steps.append(step)
    for snapshot in snapshots:
        trail.retrieval_snapshots.append(snapshot)
    return trail


def test_evaluate_agent_trails_reports_reasoning_metrics(session: Session) -> None:
    """Aggregate report captures reasoning, retrieval, and tool usage signals."""

    started_at = datetime(2024, 1, 1, tzinfo=UTC)
    completed_trail = _make_trail(
        workflow="verse_copilot",
        status="completed",
        started_at=started_at,
        plan_md="PLAN",
        steps=[
            AgentStep(step_index=0, tool="planner.generate"),
            AgentStep(step_index=1, tool="search.hybrid"),
            AgentStep(
                step_index=2,
                tool="llm.generate",
                tokens_in=120,
                tokens_out=90,
            ),
            AgentStep(step_index=3, tool="rag.compose"),
        ],
        snapshots=[
            TrailRetrievalSnapshot(
                turn_index=0,
                retrieval_hash="digest-1",
                passage_ids=["p1", "p2"],
                osis_refs=["John.1.1"],
            )
        ],
    )

    failed_trail = _make_trail(
        workflow="sermon_prep",
        status="failed",
        started_at=started_at + timedelta(hours=1),
        plan_md=None,
        steps=[
            AgentStep(step_index=0, tool="search.hybrid"),
            AgentStep(
                step_index=1,
                tool="llm.generate",
                tokens_in=60,
                tokens_out=30,
            ),
        ],
        snapshots=[
            TrailRetrievalSnapshot(
                turn_index=0,
                retrieval_hash="digest-2",
                passage_ids=["p3"],
                osis_refs=[],
            )
        ],
    )

    session.add_all([completed_trail, failed_trail])
    session.flush()

    # Link retrieval snapshot to compose step for the completed trail after flush.
    completed_snapshot = completed_trail.retrieval_snapshots[0]
    completed_snapshot.step = completed_trail.steps[-1]
    session.commit()

    report = evaluate_agent_trails(session)

    assert report.total_trails == 2
    assert report.completed_trails == 1
    assert report.failed_trails == 1
    assert report.completion_rate == pytest.approx(0.5)
    assert report.average_steps == pytest.approx(3.0)
    assert report.trails_with_plan == 1
    assert report.plan_coverage == pytest.approx(0.5)
    assert report.average_plan_length == pytest.approx(4.0)
    assert report.trails_with_retrieval == 2
    assert report.retrieval_coverage == pytest.approx(1.0)
    assert report.average_retrievals_per_trail == pytest.approx(1.0)
    assert report.retrievals_with_attached_step == 1
    assert report.retrieval_attachment_rate == pytest.approx(0.5)
    assert report.average_llm_tokens_in == pytest.approx(90.0)
    assert report.average_llm_tokens_out == pytest.approx(60.0)

    tools = {metric.tool: metric for metric in report.tool_usage}
    assert tools["search.hybrid"].step_count == 2
    assert tools["search.hybrid"].trail_count == 2
    assert tools["llm.generate"].tokens_in == 180
    assert tools["llm.generate"].tokens_out == 120


def test_evaluate_agent_trails_filters_by_window_and_workflow(
    session: Session,
) -> None:
    """Date and workflow filters restrict the evaluated trails."""

    base_time = datetime(2024, 5, 1, tzinfo=UTC)

    older_trail = _make_trail(
        workflow="verse_copilot",
        status="completed",
        started_at=base_time,
        plan_md=None,
        steps=[AgentStep(step_index=0, tool="search.hybrid")],
        snapshots=[],
    )

    newer_trail = _make_trail(
        workflow="sermon_prep",
        status="completed",
        started_at=base_time + timedelta(days=2),
        plan_md=None,
        steps=[AgentStep(step_index=0, tool="search.hybrid")],
        snapshots=[],
    )

    session.add_all([older_trail, newer_trail])
    session.commit()

    report = evaluate_agent_trails(
        session,
        since=base_time + timedelta(days=1),
        workflows=["sermon_prep"],
    )

    assert report.total_trails == 1
    assert report.completed_trails == 1
    assert report.tool_usage[0].tool == "search.hybrid"
