"""Guardrail catalogue exposure and advisory helpers."""

from __future__ import annotations

import json
from typing import Any, Mapping

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ....ai import build_guardrail_refusal
from ....ai.rag import GuardrailError
from ....ai.rag import guardrails as rag_guardrails
from ....ai.rag import workflow as rag_workflow
from ....models.ai import (
    AIFeaturesResponse,
    GuardrailAdvisory,
    GuardrailFailureMetadata,
    GuardrailSuggestion,
    DEFAULT_GUARDRAIL_SETTINGS,
)
from ....models.search import HybridSearchFilters

router = APIRouter()

__all__ = [
    "router",
    "DEFAULT_REFUSAL_MESSAGE",
    "guardrail_http_exception",
]

_DEFAULT_REFUSAL_MESSAGE = "I’m sorry, but I cannot help with that request."

if not hasattr(rag_workflow, "_format_anchor"):
    rag_workflow._format_anchor = rag_guardrails._format_anchor


@router.get("/features", response_model=AIFeaturesResponse)
def list_ai_features() -> AIFeaturesResponse:
    """Expose guardrail catalogues for client selection."""

    return AIFeaturesResponse(guardrails=DEFAULT_GUARDRAIL_SETTINGS)


_GUARDRAIL_KIND_MAP = {
    "retrieval": "retrieval",
    "generation": "generation",
    "safety": "safety",
    "ingest": "ingest",
}

_SUGGESTED_ACTIONS = {"search", "upload", "retry", "none"}


def _has_filters(filters: HybridSearchFilters | None) -> bool:
    if not filters:
        return False
    return bool(filters.model_dump(exclude_none=True))


def _normalise_filters_for_advisory(
    filters: HybridSearchFilters | None,
) -> HybridSearchFilters | None:
    """Remove empty guardrail filters before serialising suggestions."""

    if filters is None:
        return None
    data = filters.model_dump(exclude_none=True)
    if not data:
        return None
    return HybridSearchFilters(**data)


def _coerce_filters(value: object) -> HybridSearchFilters | None:
    if isinstance(value, HybridSearchFilters):
        return value if _has_filters(value) else None
    if isinstance(value, Mapping):
        try:
            candidate = HybridSearchFilters.model_validate(value)
        except Exception:  # pragma: no cover - defensive
            return None
        return candidate if _has_filters(candidate) else None
    return None


def _build_guardrail_metadata(
    exc: GuardrailError, filters: HybridSearchFilters | None
) -> GuardrailFailureMetadata:
    raw_metadata = getattr(exc, "metadata", None)
    payload: Mapping[str, Any] | None = None
    if isinstance(raw_metadata, Mapping):
        payload = raw_metadata
    elif isinstance(raw_metadata, dict):
        payload = raw_metadata

    code = "guardrail_violation"
    guardrail_value = "unknown"
    suggested_action = None
    reason: str | None = None
    embedded_filters: HybridSearchFilters | None = None

    if payload:
        if "code" in payload and isinstance(payload["code"], str):
            code = payload["code"].strip() or code
        raw_guardrail = payload.get("guardrail") or payload.get("category")
        if isinstance(raw_guardrail, str):
            guardrail_key = raw_guardrail.strip().lower()
            guardrail_value = _GUARDRAIL_KIND_MAP.get(guardrail_key, "unknown")
        raw_action = payload.get("suggested_action") or payload.get("action")
        if isinstance(raw_action, str):
            candidate_action = raw_action.strip().lower()
            if candidate_action in _SUGGESTED_ACTIONS:
                suggested_action = candidate_action
        raw_reason = payload.get("reason")
        if raw_reason is not None:
            reason = str(raw_reason)
        embedded_filters = _coerce_filters(payload.get("filters"))

    resolved_filters = _normalise_filters_for_advisory(embedded_filters or filters)

    if suggested_action not in _SUGGESTED_ACTIONS:
        if guardrail_value == "ingest":
            suggested_action = "upload"
        else:
            suggested_action = "search"

    return GuardrailFailureMetadata(
        code=code,
        guardrail=guardrail_value,  # type: ignore[arg-type]
        suggested_action=suggested_action,  # type: ignore[arg-type]
        filters=resolved_filters,
        safe_refusal=getattr(exc, "safe_refusal", False),
        reason=reason,
    )


def _guardrail_advisory(
    message: str,
    *,
    question: str | None,
    osis: str | None,
    filters: HybridSearchFilters | None,
    metadata: GuardrailFailureMetadata | None,
) -> GuardrailAdvisory:
    """Build a structured guardrail response with actionable follow-ups."""

    failure_metadata = metadata or GuardrailFailureMetadata(
        code="guardrail_violation",
        guardrail="unknown",
        suggested_action="search",
        filters=_normalise_filters_for_advisory(filters),
        safe_refusal=False,
        reason=None,
    )

    normalized_filters = failure_metadata.filters or _normalise_filters_for_advisory(filters)
    if normalized_filters is not None:
        failure_metadata = failure_metadata.model_copy(update={"filters": normalized_filters})

    suggestions: list[GuardrailSuggestion] = []

    if failure_metadata.suggested_action in {"search", "retry", "none", "upload"}:
        suggestions.append(
            GuardrailSuggestion(
                action="search",
                label="Search related passages",
                description=(
                    "Open the search workspace to inspect passages that align with your question and guardrail settings."
                ),
                query=question or None,
                osis=osis or None,
                filters=normalized_filters,
            )
        )

    if failure_metadata.suggested_action == "upload":
        suggestions.append(
            GuardrailSuggestion(
                action="upload",
                label="Upload supporting documents",
                description=(
                    "Add source material to your corpus so Theo Engine can ground future answers."
                ),
                collection=(
                    normalized_filters.collection if normalized_filters else None
                ),
            )
        )

    return GuardrailAdvisory(
        message=message,
        suggestions=suggestions,
        metadata=failure_metadata,
    )


def guardrail_http_exception(
    exc: GuardrailError,
    *,
    session: Session,
    question: str | None,
    osis: str | None,
    filters: HybridSearchFilters | None,
) -> JSONResponse:
    failure_metadata = _build_guardrail_metadata(exc, filters)
    advisory = _guardrail_advisory(
        str(exc),
        question=question,
        osis=osis,
        filters=filters,
        metadata=failure_metadata,
    )
    summary = str(exc).strip() or "Guardrail enforcement prevented a response."
    detail_text = f"Guardrail refusal: {summary}"
    advisory_payload = advisory.model_dump(mode="json")
    advisory_payload.update({"type": "guardrail_refusal", "message": summary})
    detail_payload = {
        "type": advisory_payload.get("type"),
        "message": detail_text,
        "summary": summary,
        "metadata": advisory_payload.get("metadata"),
        "suggestions": advisory_payload.get("suggestions") or [],
    }
    answer = build_guardrail_refusal(session, reason=summary)
    headers = {
        "X-Guardrail-Advisory": json.dumps(
            advisory_payload, separators=(",", ":")
        )
    }
    content = {
        "detail": detail_payload,
        "message": {"role": "assistant", "content": _DEFAULT_REFUSAL_MESSAGE},
        "answer": answer.model_dump(mode="json"),
        "guardrail_advisory": advisory_payload,
        "detail_text": detail_text,
    }
    return JSONResponse(status_code=422, content=content, headers=headers)


DEFAULT_REFUSAL_MESSAGE = _DEFAULT_REFUSAL_MESSAGE
