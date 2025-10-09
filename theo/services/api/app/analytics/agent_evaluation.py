"""Aggregate metrics that evaluate agent reasoning and tool usage."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from ..db.models import AgentTrail, TrailRetrievalSnapshot


@dataclass(frozen=True)
class ToolUsageMetric:
    """Snapshot of how frequently a specific tool step executed."""

    tool: str
    step_count: int
    trail_count: int
    tokens_in: int
    tokens_out: int


@dataclass(frozen=True)
class AgentEvaluationReport:
    """Summary statistics describing recent agent runs."""

    total_trails: int
    completed_trails: int
    failed_trails: int
    completion_rate: float
    average_steps: float
    trails_with_plan: int
    plan_coverage: float
    average_plan_length: float
    trails_with_retrieval: int
    retrieval_coverage: float
    average_retrievals_per_trail: float
    retrievals_with_attached_step: int
    retrieval_attachment_rate: float
    average_llm_tokens_in: float
    average_llm_tokens_out: float
    tool_usage: list[ToolUsageMetric]


def evaluate_agent_trails(
    session: Session,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    workflows: Iterable[str] | None = None,
) -> AgentEvaluationReport:
    """Compute aggregate metrics for agent reasoning and tooling behaviour.

    Parameters
    ----------
    session:
        SQLAlchemy session bound to the Theo Engine application database.
    since / until:
        Optional datetime bounds that restrict which trails are included. The
        ``since`` bound is inclusive, the ``until`` bound is exclusive.
    workflows:
        Optional iterable of workflow identifiers to include. When omitted all
        workflows are considered.
    """

    query: Select[tuple[AgentTrail]] = select(AgentTrail).options(
        joinedload(AgentTrail.steps),
        joinedload(AgentTrail.retrieval_snapshots).joinedload(
            TrailRetrievalSnapshot.step
        ),
    )

    if since is not None:
        query = query.where(AgentTrail.started_at >= since)
    if until is not None:
        query = query.where(AgentTrail.started_at < until)
    if workflows is not None:
        workflows_list = list(workflows)
        if workflows_list:
            query = query.where(AgentTrail.workflow.in_(workflows_list))
        else:
            return AgentEvaluationReport(
                total_trails=0,
                completed_trails=0,
                failed_trails=0,
                completion_rate=0.0,
                average_steps=0.0,
                trails_with_plan=0,
                plan_coverage=0.0,
                average_plan_length=0.0,
                trails_with_retrieval=0,
                retrieval_coverage=0.0,
                average_retrievals_per_trail=0.0,
                retrievals_with_attached_step=0,
                retrieval_attachment_rate=0.0,
                average_llm_tokens_in=0.0,
                average_llm_tokens_out=0.0,
                tool_usage=[],
            )

    trails = list(session.execute(query).unique().scalars())

    total_trails = len(trails)
    if total_trails == 0:
        return AgentEvaluationReport(
            total_trails=0,
            completed_trails=0,
            failed_trails=0,
            completion_rate=0.0,
            average_steps=0.0,
            trails_with_plan=0,
            plan_coverage=0.0,
            average_plan_length=0.0,
            trails_with_retrieval=0,
            retrieval_coverage=0.0,
            average_retrievals_per_trail=0.0,
            retrievals_with_attached_step=0,
            retrieval_attachment_rate=0.0,
            average_llm_tokens_in=0.0,
            average_llm_tokens_out=0.0,
            tool_usage=[],
        )

    completed_trails = sum(1 for trail in trails if trail.status == "completed")
    failed_trails = sum(1 for trail in trails if trail.status == "failed")
    completion_rate = completed_trails / total_trails if total_trails else 0.0

    total_steps = sum(len(trail.steps) for trail in trails)
    average_steps = total_steps / total_trails if total_trails else 0.0

    plan_lengths = [
        len(trail.plan_md or "")
        for trail in trails
        if trail.plan_md is not None and trail.plan_md.strip()
    ]
    trails_with_plan = len(plan_lengths)
    plan_coverage = trails_with_plan / total_trails if total_trails else 0.0
    average_plan_length = (
        sum(plan_lengths) / trails_with_plan if trails_with_plan else 0.0
    )

    trails_with_retrieval = sum(
        1 for trail in trails if trail.retrieval_snapshots
    )
    retrieval_coverage = (
        trails_with_retrieval / total_trails if total_trails else 0.0
    )
    total_retrievals = sum(len(trail.retrieval_snapshots) for trail in trails)
    average_retrievals = total_retrievals / total_trails if total_trails else 0.0

    retrievals_with_attached_step = sum(
        1
        for trail in trails
        for snapshot in trail.retrieval_snapshots
        if snapshot.step is not None
    )
    retrieval_attachment_rate = (
        retrievals_with_attached_step / total_retrievals
        if total_retrievals
        else 0.0
    )

    tool_counts: Counter[str] = Counter()
    tool_trails: defaultdict[str, set[str]] = defaultdict(set)
    tool_tokens_in: defaultdict[str, int] = defaultdict(int)
    tool_tokens_out: defaultdict[str, int] = defaultdict(int)

    llm_token_in_total = 0
    llm_token_out_total = 0
    llm_step_count = 0

    for trail in trails:
        for step in trail.steps:
            tool_counts[step.tool] += 1
            tool_trails[step.tool].add(trail.id)
            if step.tokens_in:
                tool_tokens_in[step.tool] += step.tokens_in
            if step.tokens_out:
                tool_tokens_out[step.tool] += step.tokens_out
            if step.tool.startswith("llm"):
                llm_step_count += 1
                if step.tokens_in:
                    llm_token_in_total += step.tokens_in
                if step.tokens_out:
                    llm_token_out_total += step.tokens_out

    average_llm_tokens_in = (
        llm_token_in_total / llm_step_count if llm_step_count else 0.0
    )
    average_llm_tokens_out = (
        llm_token_out_total / llm_step_count if llm_step_count else 0.0
    )

    tool_usage = [
        ToolUsageMetric(
            tool=tool,
            step_count=tool_counts[tool],
            trail_count=len(tool_trails[tool]),
            tokens_in=tool_tokens_in.get(tool, 0),
            tokens_out=tool_tokens_out.get(tool, 0),
        )
        for tool in sorted(tool_counts, key=tool_counts.get, reverse=True)
    ]

    return AgentEvaluationReport(
        total_trails=total_trails,
        completed_trails=completed_trails,
        failed_trails=failed_trails,
        completion_rate=completion_rate,
        average_steps=average_steps,
        trails_with_plan=trails_with_plan,
        plan_coverage=plan_coverage,
        average_plan_length=average_plan_length,
        trails_with_retrieval=trails_with_retrieval,
        retrieval_coverage=retrieval_coverage,
        average_retrievals_per_trail=average_retrievals,
        retrievals_with_attached_step=retrievals_with_attached_step,
        retrieval_attachment_rate=retrieval_attachment_rate,
        average_llm_tokens_in=average_llm_tokens_in,
        average_llm_tokens_out=average_llm_tokens_out,
        tool_usage=tool_usage,
    )


__all__ = [
    "AgentEvaluationReport",
    "ToolUsageMetric",
    "evaluate_agent_trails",
]
