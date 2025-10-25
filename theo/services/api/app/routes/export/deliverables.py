"""Routes for generating sermon and transcript deliverables."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, status

from ...errors import ExportError, Severity
from ...export.formatters import generate_export_id
from ...models.export import DeliverableRequest, DeliverableResponse
from ...workers import tasks as worker_tasks
from .utils import _DELIVERABLE_ERROR_RESPONSES

router = APIRouter()

_DELIVERABLE_FORMAT_ALIASES = {
    "md": "markdown",
}
_DELIVERABLE_FORMATS = {"markdown", "ndjson", "csv", "pdf"}


def _determine_export_id(payload: DeliverableRequest) -> str:
    if payload.type == "transcript" and payload.document_id:
        return f"transcript-{payload.document_id}"
    return generate_export_id()


def _normalise_formats(formats: Sequence[str] | None) -> list[str]:
    if not formats:
        return ["markdown"]

    normalised: list[str] = []
    seen: set[str] = set()
    for raw in formats:
        if raw is None:
            continue
        fmt = raw.strip().lower()
        if not fmt:
            continue
        fmt = _DELIVERABLE_FORMAT_ALIASES.get(fmt, fmt)
        if fmt not in _DELIVERABLE_FORMATS:
            allowed = ", ".join(sorted(_DELIVERABLE_FORMATS))
            raise ExportError(
                f"Unsupported deliverable format: {raw}",
                code="EXPORT_UNSUPPORTED_FORMAT",
                status_code=status.HTTP_400_BAD_REQUEST,
                severity=Severity.USER,
                hint=f"Choose one of: {allowed}.",
            )
        if fmt not in seen:
            normalised.append(fmt)
            seen.add(fmt)

    if not normalised:
        raise ExportError(
            "At least one deliverable format is required",
            code="EXPORT_MISSING_FORMAT",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Provide a supported format when exporting a deliverable.",
        )

    return normalised


@router.post(
    "/deliverable",
    response_model=DeliverableResponse,
    responses=_DELIVERABLE_ERROR_RESPONSES,
)
def export_deliverable(payload: DeliverableRequest) -> DeliverableResponse:
    """Generate sermon or transcript deliverables under a unified schema."""

    formats = _normalise_formats(payload.formats)
    filters = payload.filters.model_dump(exclude_none=True)
    export_id = _determine_export_id(payload)

    if payload.type == "sermon" and not payload.topic:
        raise ExportError(
            "topic is required for sermon deliverables",
            code="EXPORT_MISSING_TOPIC",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Provide a topic value to generate sermon deliverables.",
        )
    if payload.type == "transcript" and not payload.document_id:
        raise ExportError(
            "document_id is required for transcript deliverables",
            code="EXPORT_MISSING_DOCUMENT",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Select a transcript document before exporting.",
        )
    if payload.type not in {"sermon", "transcript"}:  # pragma: no cover - validation guard
        raise ExportError(
            "Unsupported deliverable type",
            code="EXPORT_UNSUPPORTED_DELIVERABLE",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Choose either sermon or transcript deliverables.",
        )

    try:
        asset_plan = worker_tasks.plan_deliverable_outputs(
            payload.type, formats, export_id
        )
    except ValueError as exc:  # pragma: no cover - guarded above
        raise ExportError(
            str(exc),
            code="EXPORT_INVALID_DELIVERABLE",
            status_code=status.HTTP_400_BAD_REQUEST,
            severity=Severity.USER,
            hint="Verify the deliverable configuration before retrying.",
        ) from exc

    task_kwargs = {
        "export_type": payload.type,
        "formats": formats,
        "export_id": export_id,
        "topic": payload.topic,
        "osis": payload.osis,
        "filters": filters,
        "model": payload.model,
        "document_id": payload.document_id,
    }
    result = worker_tasks.build_deliverable.apply_async(kwargs=task_kwargs)
    job_id = getattr(result, "id", None)

    return DeliverableResponse(
        export_id=export_id,
        status="queued",
        manifest=None,
        manifest_path=f"/exports/{export_id}/manifest.json",
        job_id=job_id,
        assets=asset_plan,
        message=f"Queued {payload.type} deliverable",
    )


__all__ = ["router", "export_deliverable"]
