"""Routes powering the personalised dashboard experience."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Iterable

from fastapi import APIRouter, Depends, Request
from sqlalchemy import Select, func, or_, select, and_, false
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session

from ..db import models
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


def _principal_subject(principal: dict | None) -> str | None:
    if not principal:
        return None
    for key in ("subject", "sub", "user_id", "id"):
        value = principal.get(key)
        if value:
            return str(value)
    return None


def _principal_team_ids(principal: dict | None) -> tuple[str, ...]:
    if not principal:
        return ()

    claims = principal.get("claims") or {}
    teams: object = (
        claims.get("teams")
        or claims.get("team_ids")
        or principal.get("teams")
        or principal.get("team_ids")
    )
    if not teams:
        return ()
    if isinstance(teams, (str, bytes)):
        teams = [teams]
    return tuple(str(team) for team in teams if team)


def _principal_tenant_ids(principal: dict | None) -> tuple[str, ...]:
    if not principal:
        return ()

    claims = principal.get("claims") or {}
    candidates: list[object] = [
        principal.get("tenant_id"),
        principal.get("tenant"),
        claims.get("tenant_id"),
        claims.get("tenant"),
        claims.get("tenants"),
    ]

    tenant_ids: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        if isinstance(candidate, (str, bytes)):
            tenant_ids.append(str(candidate))
        elif isinstance(candidate, (list, tuple, set)):
            tenant_ids.extend(str(item) for item in candidate if item)

    return tuple({tenant for tenant in tenant_ids if tenant})


def _ownership_predicate(model, principal: dict | None):
    """Return a SQLAlchemy predicate restricting ``model`` to the principal."""

    if not principal:
        return None

    subject = _principal_subject(principal)
    teams = _principal_team_ids(principal)
    tenants = _principal_tenant_ids(principal)

    expressions = []

    if subject:
        for attribute in ("created_by", "user_id", "owner_id", "author_id"):
            column = getattr(model, attribute, None)
            if column is not None:
                expressions.append(column == subject)

    if teams:
        for attribute in ("team_id", "owner_team_id", "group_id"):
            column = getattr(model, attribute, None)
            if column is not None:
                expressions.append(column.in_(teams))

    if tenants:
        column = getattr(model, "tenant_id", None)
        if column is not None:
            expressions.append(column.in_(tenants))

    if not expressions:
        return None

    if len(expressions) == 1:
        return expressions[0]
    return or_(*expressions)


def _apply_scope(stmt: Select, model, principal: dict | None) -> Select:
    predicate = _ownership_predicate(model, principal)
    if predicate is not None:
        stmt = stmt.where(predicate)
    return stmt


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
    principal: dict | None,
    current_start: datetime,
    previous_start: datetime,
) -> tuple[int, int]:
    """Return counts for the current and previous periods using ``column`` timestamps."""

    current_stmt = select(func.count()).select_from(model).where(column >= current_start)
    current_stmt = _apply_scope(current_stmt, model, principal)
    current_count = session.execute(current_stmt).scalar_one()

    previous_stmt = (
        select(func.count())
        .select_from(model)
        .where(column >= previous_start, column < current_start)
    )
    previous_stmt = _apply_scope(previous_stmt, model, principal)
    previous_count = session.execute(previous_stmt).scalar_one()

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


def _count_total(session: Session, model, *, principal: dict | None) -> int:
    stmt: Select[int] = select(func.count()).select_from(model)
    stmt = _apply_scope(stmt, model, principal)
    return int(session.execute(stmt).scalar_one() or 0)


def _collect_activities(
    session: Session, *, principal: dict | None, limit: int = 8
) -> list[DashboardActivity]:
    """Gather a blended feed from recent domain artefacts."""

    activities: list[DashboardActivity] = []

    document_stmt = (
        select(models.Document)
        .order_by(models.Document.created_at.desc())
        .limit(limit)
    )
    document_stmt = _apply_scope(document_stmt, models.Document, principal)
    document_rows = session.execute(document_stmt).scalars()
    for document in document_rows:
        activities.append(
            DashboardActivity(
                id=f"document-{document.id}",
                type="document_ingested",
                title=document.title or "Document uploaded",
                description=document.collection,
                occurred_at=document.created_at,
                href=f"/doc/{document.id}",
            )
        )

    note_stmt = (
        select(models.ResearchNote)
        .order_by(models.ResearchNote.created_at.desc())
        .limit(limit)
    )
    note_stmt = _apply_scope(note_stmt, models.ResearchNote, principal)
    note_rows = session.execute(note_stmt).scalars()
    for note in note_rows:
        activities.append(
            DashboardActivity(
                id=f"note-{note.id}",
                type="note_created",
                title=note.title or note.osis,
                description=(note.stance or note.claim_type),
                occurred_at=note.created_at,
                href=f"/research/notes/{note.id}",
            )
        )

    discovery_stmt = (
        select(models.Discovery)
        .order_by(models.Discovery.created_at.desc())
        .limit(limit)
    )
    discovery_stmt = _apply_scope(discovery_stmt, models.Discovery, principal)
    discovery_rows = session.execute(discovery_stmt).scalars()
    for discovery in discovery_rows:
        activities.append(
            DashboardActivity(
                id=f"discovery-{discovery.id}",
                type="discovery_published",
                title=discovery.title,
                description=discovery.description,
                occurred_at=discovery.created_at,
                href="/discoveries",
            )
        )

    notebook_stmt = (
        select(models.Notebook)
        .order_by(models.Notebook.updated_at.desc())
        .limit(limit)
    )
    notebook_stmt = _apply_scope(notebook_stmt, models.Notebook, principal)
    notebook_rows = session.execute(notebook_stmt).scalars()
    for notebook in notebook_rows:
        activities.append(
            DashboardActivity(
                id=f"notebook-{notebook.id}",
                type="notebook_updated",
                title=notebook.title,
                description=notebook.description,
                occurred_at=notebook.updated_at,
                href=f"/notebooks/{notebook.id}",
            )
        )

    activities.sort(key=lambda item: item.occurred_at, reverse=True)
    return activities[:limit]


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

    principal = _principal_from_request(request)

    now = datetime.now(UTC)
    current_start = now - timedelta(days=7)
    previous_start = current_start - timedelta(days=7)

    documents_current, documents_previous = _period_counts(
        session,
        models.Document,
        models.Document.created_at,
        principal=principal,
        current_start=current_start,
        previous_start=previous_start,
    )
    notes_current, notes_previous = _period_counts(
        session,
        models.ResearchNote,
        models.ResearchNote.created_at,
        principal=principal,
        current_start=current_start,
        previous_start=previous_start,
    )
    discoveries_current, discoveries_previous = _period_counts(
        session,
        models.Discovery,
        models.Discovery.created_at,
        principal=principal,
        current_start=current_start,
        previous_start=previous_start,
    )
    notebooks_current, notebooks_previous = _period_counts(
        session,
        models.Notebook,
        models.Notebook.updated_at,
        principal=principal,
        current_start=current_start,
        previous_start=previous_start,
    )

    metrics = [
        _build_metric(
            metric_id="documents",
            label="Documents indexed",
            value=_count_total(session, models.Document, principal=principal),
            unit=None,
            delta=_percentage_delta(documents_current, documents_previous),
        ),
        _build_metric(
            metric_id="notes",
            label="Research notes",
            value=_count_total(session, models.ResearchNote, principal=principal),
            unit=None,
            delta=_percentage_delta(notes_current, notes_previous),
        ),
        _build_metric(
            metric_id="discoveries",
            label="Discoveries surfaced",
            value=_count_total(session, models.Discovery, principal=principal),
            unit=None,
            delta=_percentage_delta(discoveries_current, discoveries_previous),
        ),
        _build_metric(
            metric_id="notebooks",
            label="Active notebooks",
            value=_count_total(session, models.Notebook, principal=principal),
            unit=None,
            delta=_percentage_delta(notebooks_current, notebooks_previous),
        ),
    ]

    activity = _collect_activities(session, principal=principal)
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
