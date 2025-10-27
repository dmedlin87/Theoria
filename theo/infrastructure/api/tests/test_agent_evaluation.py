"""Tests for agent evaluation analytics helpers."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from theo.infrastructure.api.app.analytics.agent_evaluation import (
    _build_trail_query,
    _compute_completion_metrics,
    _compute_retrieval_metrics,
    _compute_tool_metrics,
)
from theo.application.facades.database import get_engine
from theo.adapters.persistence.models import (
    AgentStep,
    AgentTrail,
    TrailRetrievalSnapshot,
)


def _seed_trails(session: Session) -> list[AgentTrail]:
    """Populate the database with representative trail records."""

    session.execute(delete(TrailRetrievalSnapshot))
    session.execute(delete(AgentStep))
    session.execute(delete(AgentTrail))
    session.commit()

    now = datetime.now(timezone.utc)

    completed_trail = AgentTrail(
        workflow="workflow-a",
        status="completed",
        plan_md="Plan text",
        started_at=now,
    )
    completed_step_llm = AgentStep(
        step_index=0,
        tool="llm.generate",
        tokens_in=100,
        tokens_out=150,
        created_at=now,
    )
    completed_step_search = AgentStep(
        step_index=1,
        tool="search.lookup",
        tokens_in=None,
        tokens_out=None,
        created_at=now,
    )
    completed_trail.steps.extend([completed_step_llm, completed_step_search])

    completed_trail.retrieval_snapshots.extend(
        [
            TrailRetrievalSnapshot(
                turn_index=0,
                retrieval_hash="hash-a",
                passage_ids=["passage-1"],
                osis_refs=["John.1.1"],
                step=completed_step_llm,
                created_at=now,
            ),
            TrailRetrievalSnapshot(
                turn_index=1,
                retrieval_hash="hash-b",
                passage_ids=["passage-2"],
                osis_refs=["John.1.2"],
                created_at=now,
            ),
        ]
    )

    failed_trail = AgentTrail(
        workflow="workflow-b",
        status="failed",
        plan_md=None,
        started_at=now,
    )
    failed_step_llm = AgentStep(
        step_index=0,
        tool="llm.refine",
        tokens_in=50,
        tokens_out=60,
        created_at=now,
    )
    failed_trail.steps.append(failed_step_llm)
    failed_trail.retrieval_snapshots.append(
        TrailRetrievalSnapshot(
            turn_index=0,
            retrieval_hash="hash-c",
            passage_ids=["passage-3"],
            osis_refs=["John.1.3"],
            created_at=now,
        )
    )

    session.add_all([completed_trail, failed_trail])
    session.commit()

    query = _build_trail_query()
    assert query is not None
    return list(session.execute(query).unique().scalars())


def test_build_trail_query_filters_workflows() -> None:
    engine = get_engine()
    with Session(engine) as session:
        _seed_trails(session)

        query = _build_trail_query(workflows=["workflow-a"])
        assert query is not None
        trails = list(session.execute(query).unique().scalars())

        assert len(trails) == 1
        assert trails[0].workflow == "workflow-a"


def test_compute_completion_metrics() -> None:
    engine = get_engine()
    with Session(engine) as session:
        trails = _seed_trails(session)

        metrics = _compute_completion_metrics(trails)

        assert metrics["total_trails"] == 2
        assert metrics["completed_trails"] == 1
        assert metrics["failed_trails"] == 1
        assert metrics["completion_rate"] == pytest.approx(0.5)
        assert metrics["average_steps"] == pytest.approx(1.5)
        assert metrics["trails_with_plan"] == 1
        assert metrics["plan_coverage"] == pytest.approx(0.5)
        assert metrics["average_plan_length"] == pytest.approx(len("Plan text"))


def test_compute_retrieval_metrics() -> None:
    engine = get_engine()
    with Session(engine) as session:
        trails = _seed_trails(session)

        metrics = _compute_retrieval_metrics(trails)

        assert metrics["trails_with_retrieval"] == 2
        assert metrics["retrieval_coverage"] == pytest.approx(1.0)
        assert metrics["average_retrievals_per_trail"] == pytest.approx(1.5)
        assert metrics["retrievals_with_attached_step"] == 1
        assert metrics["retrieval_attachment_rate"] == pytest.approx(1 / 3)


def test_compute_tool_metrics() -> None:
    engine = get_engine()
    with Session(engine) as session:
        trails = _seed_trails(session)

        metrics = _compute_tool_metrics(trails)

        assert metrics["average_llm_tokens_in"] == pytest.approx(75.0)
        assert metrics["average_llm_tokens_out"] == pytest.approx(105.0)

        usage_by_tool = {metric.tool: metric for metric in metrics["tool_usage"]}

        llm_generate = usage_by_tool["llm.generate"]
        assert llm_generate.step_count == 1
        assert llm_generate.trail_count == 1
        assert llm_generate.tokens_in == 100
        assert llm_generate.tokens_out == 150

        llm_refine = usage_by_tool["llm.refine"]
        assert llm_refine.step_count == 1
        assert llm_refine.trail_count == 1
        assert llm_refine.tokens_in == 50
        assert llm_refine.tokens_out == 60

        search_lookup = usage_by_tool["search.lookup"]
        assert search_lookup.step_count == 1
        assert search_lookup.trail_count == 1
        assert search_lookup.tokens_in == 0
        assert search_lookup.tokens_out == 0
