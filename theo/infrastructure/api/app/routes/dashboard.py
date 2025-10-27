"""Routes powering the personalised dashboard experience."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Iterable

from fastapi import APIRouter, Depends, Request
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from theo.adapters.persistence import models
from theo.application.facades.database import get_session

from ..models.dashboard import (
    DashboardActivity,
    DashboardMetric,
    DashboardQuickAction,
    DashboardSummary,
    DashboardUserSummary,
    MetricTrend,
)

router = APIRouter()


def _principal_from_request(request: Request) -> dict | None:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, dict):
        return principal
    return None


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def _resolve_user_summary(request: Request) -> DashboardUserSummary:
    principal = _principal_from_request(request) or {}
    name = str(principal.get("name") or principal.get("subject") or "Researcher")
    plan = principal.get("plan")
    timezone = principal.get("timezone")
    last_login = _parse_datetime(principal.get("last_login"))
    return DashboardUserSummary(name=name, plan=plan, timezone=timezone, last_login=last_login)


def _period_counts(
    session: Session,
    model,
    column,
    *,
    current_start: datetime,
    previous_start: datetime,
) -> tuple[int, int]:
    """Return counts for the current and previous periods using ``column`` timestamps."""

    current_count = session.execute(
        select(func.count()).select_from(model).where(column >= current_start)
    ).scalar_one()

    previous_count = session.execute(
        select(func.count()).select_from(model).where(column >= previous_start, column < current_start)
    ).scalar_one()

    return int(current_count or 0), int(previous_count or 0)


def _percentage_delta(current: int, previous: int) -> float | None:
    if previous == 0 and current == 0:
        return None
    if previous == 0:
        return 100.0
    change = ((current - previous) / previous) * 100
    return round(change, 1)


def _trend_from_delta(delta: float | None) -> MetricTrend:
    if delta is None:
        return MetricTrend.FLAT
    if delta > 1:
        return MetricTrend.UP
    if delta < -1:
        return MetricTrend.DOWN
    return MetricTrend.FLAT


def _build_metric(
    *,
    metric_id: str,
    label: str,
    value: int,
    unit: str | None,
    delta: float | None,
) -> DashboardMetric:
    return DashboardMetric(
        id=metric_id,
        label=label,
        value=float(value),
        unit=unit,
        delta_percentage=delta,
        trend=_trend_from_delta(delta),
    )


def _count_total(session: Session, model) -> int:
    stmt: Select[int] = select(func.count()).select_from(model)
    return int(session.execute(stmt).scalar_one() or 0)


def _collect_activities(session: Session, limit: int = 8) -> list[DashboardActivity]:
    """Gather a blended feed from recent domain artefacts."""

    activity_entries: list[DashboardActivity] = []

    document_rows = session.execute(
        select(models.Document).order_by(models.Document.created_at.desc()).limit(limit)
    ).scalars()
    activity_entries.extend(
        DashboardActivity(
            id=f"document-{document.id}",
            type="document_ingested",
            title=document.title or "Document uploaded",
            description=document.collection,
            occurred_at=document.created_at,
            href=f"/doc/{document.id}",
        )
        for document in document_rows
    )

    note_rows = session.execute(
        select(models.ResearchNote).order_by(models.ResearchNote.created_at.desc()).limit(limit)
    ).scalars()
    activity_entries.extend(
        DashboardActivity(
            id=f"note-{note.id}",
            type="note_created",
            title=note.title or note.osis,
            description=(note.stance or note.claim_type),
            occurred_at=note.created_at,
            href=f"/research/notes/{note.id}",
        )
        for note in note_rows
    )

    discovery_rows = session.execute(
        select(models.Discovery).order_by(models.Discovery.created_at.desc()).limit(limit)
    ).scalars()
    activity_entries.extend(
        DashboardActivity(
            id=f"discovery-{discovery.id}",
            type="discovery_published",
            title=discovery.title,
            description=discovery.description,
            occurred_at=discovery.created_at,
            href="/discoveries",
        )
        for discovery in discovery_rows
    )

    notebook_rows = session.execute(
        select(models.Notebook).order_by(models.Notebook.updated_at.desc()).limit(limit)
    ).scalars()
    activity_entries.extend(
        DashboardActivity(
            id=f"notebook-{notebook.id}",
            type="notebook_updated",
            title=notebook.title,
            description=notebook.description,
            occurred_at=notebook.updated_at,
            href=f"/notebooks/{notebook.id}",
        )
        for notebook in notebook_rows
    )

    activity_entries.sort(key=lambda item: item.occurred_at, reverse=True)
    return activity_entries[:limit]


def _quick_actions() -> list[DashboardQuickAction]:
    return [
        DashboardQuickAction(
            id="search",
            label="Search the corpus",
            description="Keyword, verse, and topical search",
            href="/search",
            icon="🔍",
        ),
        DashboardQuickAction(
            id="chat",
            label="Open Theo Copilot",
            description="Collaborate with the research assistant",
            href="/chat",
            icon="🤖",
        ),
        DashboardQuickAction(
            id="upload",
            label="Ingest new sources",
            description="Upload PDFs or transcripts",
            href="/upload",
            icon="📤",
        ),
        DashboardQuickAction(
            id="notebooks",
            label="Review notebooks",
            description="Organise study notes",
            href="/notebooks",
            icon="📓",
        ),
    ]


@router.get("/", response_model=DashboardSummary)
def get_dashboard_summary(
    request: Request, session: Session = Depends(get_session)
) -> DashboardSummary:
    """Return personalised dashboard content for the active user."""

    now = datetime.now(UTC)
    current_start = now - timedelta(days=7)
    previous_start = current_start - timedelta(days=7)

    documents_current, documents_previous = _period_counts(
        session,
        models.Document,
        models.Document.created_at,
        current_start=current_start,
        previous_start=previous_start,
    )
    notes_current, notes_previous = _period_counts(
        session,
        models.ResearchNote,
        models.ResearchNote.created_at,
        current_start=current_start,
        previous_start=previous_start,
    )
    discoveries_current, discoveries_previous = _period_counts(
        session,
        models.Discovery,
        models.Discovery.created_at,
        current_start=current_start,
        previous_start=previous_start,
    )
    notebooks_current, notebooks_previous = _period_counts(
        session,
        models.Notebook,
        models.Notebook.updated_at,
        current_start=current_start,
        previous_start=previous_start,
    )

    metrics = [
        _build_metric(
            metric_id="documents",
            label="Documents indexed",
            value=_count_total(session, models.Document),
            unit=None,
            delta=_percentage_delta(documents_current, documents_previous),
        ),
        _build_metric(
            metric_id="notes",
            label="Research notes",
            value=_count_total(session, models.ResearchNote),
            unit=None,
            delta=_percentage_delta(notes_current, notes_previous),
        ),
        _build_metric(
            metric_id="discoveries",
            label="Discoveries surfaced",
            value=_count_total(session, models.Discovery),
            unit=None,
            delta=_percentage_delta(discoveries_current, discoveries_previous),
        ),
        _build_metric(
            metric_id="notebooks",
            label="Active notebooks",
            value=_count_total(session, models.Notebook),
            unit=None,
            delta=_percentage_delta(notebooks_current, notebooks_previous),
        ),
    ]

    activity = _collect_activities(session)
    quick_actions = _quick_actions()
    user = _resolve_user_summary(request)

    return DashboardSummary(
        generated_at=now,
        user=user,
        metrics=metrics,
        activity=activity,
        quick_actions=quick_actions,
    )


__all__ = ["router", "get_dashboard_summary"]
