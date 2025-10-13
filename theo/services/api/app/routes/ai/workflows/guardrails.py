"""Guardrail response helpers shared across workflow endpoints."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from theo.services.api.app.ai import build_guardrail_refusal
from theo.services.api.app.ai.rag import GuardrailError, RAGAnswer
from theo.services.api.app.errors import AIWorkflowError, Severity
from theo.services.api.app.models.ai import (
    GuardrailAdvisory,
    GuardrailFailureMetadata,
    GuardrailSuggestion,
)
from theo.services.api.app.models.search import HybridSearchFilters
from .utils import has_filters


DEFAULT_REFUSAL_MESSAGE = "I’m sorry, but I cannot help with that request."
_GUARDRAIL_KIND_MAP = {
    "retrieval": "retrieval",
    "generation": "generation",
    "safety": "safety",
    "ingest": "ingest",
}
_SUGGESTED_ACTIONS = {"search", "upload", "retry", "none"}


def normalise_filters_for_advisory(
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
        return value if has_filters(value) else None
    if isinstance(value, Mapping):
        try:
            candidate = HybridSearchFilters.model_validate(value)
        except Exception:  # pragma: no cover - defensive
            return None
        return candidate if has_filters(candidate) else None
    return None


def build_guardrail_metadata(
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

    resolved_filters = normalise_filters_for_advisory(embedded_filters or filters)

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


def guardrail_advisory(
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
        filters=normalise_filters_for_advisory(filters),
        safe_refusal=False,
        reason=None,
    )

    normalized_filters = failure_metadata.filters or normalise_filters_for_advisory(filters)
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


def _normalise_error_code(code: str | None) -> str:
    slug = (code or "guardrail_violation").strip()
    if not slug:
        slug = "guardrail_violation"
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", slug).strip("_") or "GUARDRAIL_VIOLATION"
    formatted = slug.upper()
    if not formatted.startswith("AI_"):
        formatted = f"AI_{formatted}"
    return formatted


def guardrail_http_exception(
    exc: GuardrailError,
    *,
    session: Session,
    question: str | None,
    osis: str | None,
    filters: HybridSearchFilters | None,
) -> JSONResponse:
    failure_metadata = build_guardrail_metadata(exc, filters)
    advisory = guardrail_advisory(
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
    filters_payload = (
        failure_metadata.filters.model_dump(exclude_none=True)
        if failure_metadata.filters
        else None
    )
    error_data: dict[str, Any] = {
        "guardrail": failure_metadata.guardrail,
        "suggested_action": failure_metadata.suggested_action,
        "safe_refusal": failure_metadata.safe_refusal,
        "summary": summary,
    }
    if filters_payload:
        error_data["filters"] = filters_payload
    if failure_metadata.reason:
        error_data["reason"] = failure_metadata.reason
    raw_metadata = getattr(exc, "metadata", None)
    if isinstance(raw_metadata, Mapping):
        error_data["metadata"] = dict(raw_metadata)

    error = AIWorkflowError(
        detail_text,
        code=_normalise_error_code(failure_metadata.code),
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        severity=Severity.USER,
        hint=failure_metadata.reason,
        data=error_data,
    )
    answer = build_guardrail_refusal(session, reason=summary)
    headers = {
        "X-Guardrail-Advisory": json.dumps(
            advisory_payload, separators=(",", ":")
        )
    }
    payload = error.to_payload()
    payload["detail"] = detail_payload
    payload["message"] = {"role": "assistant", "content": DEFAULT_REFUSAL_MESSAGE}
    payload["answer"] = answer.model_dump(mode="json")
    payload["guardrail_advisory"] = advisory_payload
    payload["detail_text"] = detail_text
    return JSONResponse(status_code=error.status_code, content=payload, headers=headers)


def extract_refusal_text(answer: RAGAnswer) -> str:
    """Normalise a guardrailed completion for user-facing chat responses."""

    completion = answer.model_output or ""
    if completion:
        lowered = completion.lower()
        marker_index = lowered.rfind("sources:")
        if marker_index != -1:
            completion = completion[:marker_index]
        completion = completion.strip()
    if not completion:
        completion = (answer.summary or "").strip()
    if not completion:
        completion = DEFAULT_REFUSAL_MESSAGE
    return completion


__all__ = [
    "DEFAULT_REFUSAL_MESSAGE",
    "build_guardrail_metadata",
    "guardrail_advisory",
    "guardrail_http_exception",
    "extract_refusal_text",
    "normalise_filters_for_advisory",
]
