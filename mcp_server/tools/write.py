"""Handlers for MCP write tools with commit/dry-run semantics."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterator, cast
from uuid import uuid4

from fastapi import Header, HTTPException
from fastapi.params import Header as HeaderInfo
from opentelemetry import trace

from .. import schemas
from ..security import WriteSecurityError, get_write_security_policy
from .read import _session_scope
from theo.services.api.app.models.jobs import HNSWRefreshJobRequest
from theo.services.api.app.research.notes import (
    create_research_note,
    generate_research_note_preview,
)
from theo.services.api.app.research.evidence_cards import (
    create_evidence_card,
    preview_evidence_card,
)
from theo.services.api.app.routes.jobs import enqueue_refresh_hnsw_job

LOGGER = logging.getLogger(__name__)
_TRACER = trace.get_tracer("theo.mcp.write")


def _normalize_header(value: Any) -> str | None:
    if isinstance(value, HeaderInfo):
        return None
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


@contextmanager
def _write_instrumentation(
    tool: str,
    request: schemas.ToolRequestBase,
    end_user_id: str,
    tenant_id: str | None,
    idempotency_key: str | None,
) -> Iterator[tuple[str, Any]]:
    run_id = str(uuid4())
    with _TRACER.start_as_current_span(f"mcp.{tool}") as span:
        span.set_attribute("tool.name", tool)
        span.set_attribute("tool.request_id", request.request_id)
        span.set_attribute("tool.end_user_id", end_user_id)
        span.set_attribute("tool.commit", request.commit)
        if tenant_id:
            span.set_attribute("tool.tenant_id", tenant_id)
        if idempotency_key:
            span.set_attribute("tool.idempotency_key", idempotency_key)
        LOGGER.info(
            "mcp.tool.invoked",
            extra={
                "event": f"mcp.{tool}",
                "tool": tool,
                "request_id": request.request_id,
                "end_user_id": end_user_id,
                "tenant_id": tenant_id,
                "commit": request.commit,
                "idempotency_key": idempotency_key,
                "run_id": run_id,
            },
        )
        yield run_id, span


def _note_preview_payload(preview: Any) -> Dict[str, Any]:
    return {
        "osis": getattr(preview, "osis", None),
        "title": getattr(preview, "title", None),
        "stance": getattr(preview, "stance", None),
        "claim_type": getattr(preview, "claim_type", None),
        "tags": list(getattr(preview, "tags", []) or []),
        "body": getattr(preview, "body", None),
    }


def _evidence_preview_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    preview = dict(payload)
    tags = preview.get("tags") or []
    if isinstance(tags, list):
        preview["tags"] = sorted({tag.strip() for tag in tags if isinstance(tag, str) and tag.strip()})
    return preview


async def note_write(
    request: schemas.NoteWriteRequest,
    end_user_id: str = Header(..., alias="X-End-User-Id"),
    tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> schemas.NoteWriteResponse:
    tenant_id = _normalize_header(tenant_id)
    idempotency_key = _normalize_header(idempotency_key)
    policy = get_write_security_policy()
    cached = policy.resolve_cached_response(
        "note_write", request.commit, tenant_id, end_user_id, idempotency_key
    )
    if cached is not None:
        return cast(schemas.NoteWriteResponse, cached)

    try:
        policy.ensure_allowed("note_write", request.commit, tenant_id, end_user_id)
        policy.enforce_rate_limit("note_write", request.commit, tenant_id, end_user_id)
    except WriteSecurityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    with _write_instrumentation("note_write", request, end_user_id, tenant_id, idempotency_key) as (
        run_id,
        span,
    ):
        with _session_scope() as session:
            if request.commit:
                note = create_research_note(
                    session,
                    osis=request.osis,
                    body=request.body,
                    title=request.title,
                    stance=request.stance,
                    claim_type=request.claim_type,
                    tags=request.tags,
                    evidences=request.evidences,
                    commit=True,
                    request_id=request.request_id,
                    end_user_id=end_user_id,
                    tenant_id=tenant_id,
                )
                response = schemas.NoteWriteResponse(
                    request_id=request.request_id,
                    run_id=run_id,
                    commit=True,
                    note_id=getattr(note, "id", None),
                    status="accepted",
                    preview=None,
                )
            else:
                preview = generate_research_note_preview(
                    session,
                    osis=request.osis,
                    body=request.body,
                    title=request.title,
                    stance=request.stance,
                    claim_type=request.claim_type,
                    tags=request.tags,
                    evidences=request.evidences,
                )
                response = schemas.NoteWriteResponse(
                    request_id=request.request_id,
                    run_id=run_id,
                    commit=False,
                    note_id=None,
                    status="preview",
                    preview=_note_preview_payload(preview),
                )
        span.set_attribute("tool.commit", response.commit)

    if request.commit and idempotency_key:
        policy.store_idempotent_response(
            "note_write", tenant_id, end_user_id, idempotency_key, response
        )

    return response


async def index_refresh(
    request: schemas.IndexRefreshRequest,
    end_user_id: str = Header(..., alias="X-End-User-Id"),
    tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> schemas.IndexRefreshResponse:
    tenant_id = _normalize_header(tenant_id)
    idempotency_key = _normalize_header(idempotency_key)
    policy = get_write_security_policy()
    cached = policy.resolve_cached_response(
        "index_refresh", request.commit, tenant_id, end_user_id, idempotency_key
    )
    if cached is not None:
        return cast(schemas.IndexRefreshResponse, cached)

    try:
        policy.ensure_allowed("index_refresh", request.commit, tenant_id, end_user_id)
        policy.enforce_rate_limit("index_refresh", request.commit, tenant_id, end_user_id)
    except WriteSecurityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    with _write_instrumentation("index_refresh", request, end_user_id, tenant_id, idempotency_key) as (
        run_id,
        span,
    ):
        if request.commit:
            with _session_scope() as session:
                job_request = HNSWRefreshJobRequest(
                    sample_queries=request.sample_queries,
                    top_k=request.top_k,
                )
                job_status = enqueue_refresh_hnsw_job(job_request, session=session)
            job_payload: Dict[str, Any] = job_status.model_dump()
            response = schemas.IndexRefreshResponse(
                request_id=request.request_id,
                run_id=run_id,
                commit=True,
                accepted=True,
                message="refresh enqueued",
                job=job_payload,
                preview=None,
            )
        else:
            preview = {
                "sample_queries": request.sample_queries,
                "top_k": request.top_k,
            }
            response = schemas.IndexRefreshResponse(
                request_id=request.request_id,
                run_id=run_id,
                commit=False,
                accepted=False,
                message="preview",
                job=None,
                preview=preview,
            )
        span.set_attribute("tool.commit", response.commit)
        if response.job:
            span.set_attribute("tool.job_id", response.job.get("id"))

    if request.commit and idempotency_key:
        policy.store_idempotent_response(
            "index_refresh", tenant_id, end_user_id, idempotency_key, response
        )

    return response


async def evidence_card_create(
    request: schemas.EvidenceCardCreateRequest,
    end_user_id: str = Header(..., alias="X-End-User-Id"),
    tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
) -> schemas.EvidenceCardCreateResponse:
    tenant_id = _normalize_header(tenant_id)
    idempotency_key = _normalize_header(idempotency_key)
    policy = get_write_security_policy()
    cached = policy.resolve_cached_response(
        "evidence_card_create", request.commit, tenant_id, end_user_id, idempotency_key
    )
    if cached is not None:
        return cast(schemas.EvidenceCardCreateResponse, cached)

    try:
        policy.ensure_allowed("evidence_card_create", request.commit, tenant_id, end_user_id)
        policy.enforce_rate_limit("evidence_card_create", request.commit, tenant_id, end_user_id)
    except WriteSecurityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    with _write_instrumentation(
        "evidence_card_create", request, end_user_id, tenant_id, idempotency_key
    ) as (run_id, span):
        with _session_scope() as session:
            if request.commit:
                card = create_evidence_card(
                    session,
                    osis=request.osis,
                    claim_summary=request.claim_summary,
                    evidence=request.evidence,
                    tags=request.tags,
                    commit=True,
                    request_id=request.request_id,
                    end_user_id=end_user_id,
                    tenant_id=tenant_id,
                )
                response = schemas.EvidenceCardCreateResponse(
                    request_id=request.request_id,
                    run_id=run_id,
                    commit=True,
                    evidence_id=getattr(card, "id", None),
                    status="accepted",
                    preview=None,
                )
            else:
                preview = preview_evidence_card(
                    session,
                    osis=request.osis,
                    claim_summary=request.claim_summary,
                    evidence=request.evidence,
                    tags=request.tags,
                )
                response = schemas.EvidenceCardCreateResponse(
                    request_id=request.request_id,
                    run_id=run_id,
                    commit=False,
                    evidence_id=None,
                    status="preview",
                    preview=_evidence_preview_payload(preview),
                )
        span.set_attribute("tool.commit", response.commit)
        if response.preview:
            span.set_attribute("tool.preview_tags", len(response.preview.get("tags", []) or []))

    if request.commit and idempotency_key:
        policy.store_idempotent_response(
            "evidence_card_create", tenant_id, end_user_id, idempotency_key, response
        )

    return response


__all__ = ["note_write", "index_refresh", "evidence_card_create"]
