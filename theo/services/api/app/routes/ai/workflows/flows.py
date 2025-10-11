"""Workflow execution routes for ministry experiences."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, TypeAlias

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from theo.services.api.app.ai import (
    generate_comparative_analysis,
    generate_devotional_flow,
    generate_multimedia_digest,
    generate_sermon_prep_outline,
    generate_verse_brief,
    run_corpus_curation,
    run_research_reconciliation,
)
from theo.services.api.app.ai.passage import PassageResolutionError, resolve_passage_reference
from theo.services.api.app.ai.rag import (
    CollaborationResponse,
    ComparativeAnalysisResponse,
    CorpusCurationReport,
    DevotionalResponse,
    GuardrailError,
    MultimediaDigestResponse,
    SermonPrepResponse,
    VerseCopilotResponse,
)
from theo.services.api.app.ai.trails import TrailService
from theo.services.api.app.core.database import get_session
from theo.services.api.app.models.ai import (
    CollaborationRequest,
    ComparativeAnalysisRequest,
    CorpusCurationRequest,
    DevotionalRequest,
    MultimediaDigestRequest,
    SermonPrepRequest,
    VerseCopilotRequest,
)
from .guardrails import guardrail_http_exception


if TYPE_CHECKING:
    from fastapi.responses import JSONResponse

    VerseCopilotReturn: TypeAlias = VerseCopilotResponse | JSONResponse
    SermonPrepReturn: TypeAlias = SermonPrepResponse | JSONResponse
    DevotionalReturn: TypeAlias = DevotionalResponse | JSONResponse
    CollaborationReturn: TypeAlias = CollaborationResponse | JSONResponse
    ComparativeReturn: TypeAlias = ComparativeAnalysisResponse | JSONResponse
    MultimediaReturn: TypeAlias = MultimediaDigestResponse | JSONResponse
else:  # pragma: no cover - runtime type hints for FastAPI decorators
    VerseCopilotReturn: TypeAlias = VerseCopilotResponse
    SermonPrepReturn: TypeAlias = SermonPrepResponse
    DevotionalReturn: TypeAlias = DevotionalResponse
    CollaborationReturn: TypeAlias = CollaborationResponse
    ComparativeReturn: TypeAlias = ComparativeAnalysisResponse
    MultimediaReturn: TypeAlias = MultimediaDigestResponse

router = APIRouter()
_BAD_REQUEST_RESPONSE = {status.HTTP_400_BAD_REQUEST: {"description": "Invalid request"}}

VERSE_COPILOT_PLAN = "\n".join(
    [
        "- Retrieve relevant passages with hybrid search",
        "- Generate a grounded answer with the configured LLM",
        "- Return citations and recommended follow-up prompts",
    ]
)

SERMON_PREP_PLAN = "\n".join(
    [
        "- Search for passages aligned to the sermon topic",
        "- Summarise retrieved context into a guardrailed outline",
        "- Surface key points and citations for sermon preparation",
    ]
)

MULTIMEDIA_PLAN = "\n".join(
    [
        "- Retrieve recent multimedia passages with hybrid search",
        "- Summarise cross-media highlights with the configured LLM",
        "- Return grounded insights with supporting citations",
    ]
)

DEVOTIONAL_PLAN = "\n".join(
    [
        "- Retrieve reflective passages tied to the devotional focus",
        "- Compose a prayerful reflection grounded in citations",
        "- Suggest prayer prompts rooted in retrieved passages",
    ]
)

COLLABORATION_PLAN = "\n".join(
    [
        "- Gather sources representing each supplied viewpoint",
        "- Reconcile perspectives using a grounded synthesis",
        "- Surface shared insights with cited support",
    ]
)

CORPUS_CURATION_PLAN = "\n".join(
    [
        "- Load documents added within the requested window",
        "- Summarise each document by topic and collection",
        "- Produce a curator-ready digest of repository changes",
    ]
)


@router.post(
    "/verse",
    response_model=VerseCopilotResponse,
    response_model_exclude_none=True,
)
def verse_copilot(
    payload: VerseCopilotRequest,
    session: Session = Depends(get_session),
) -> VerseCopilotReturn:
    trail_service = TrailService(session)
    osis_value = (payload.osis or "").strip() or None
    passage_value = (payload.passage or "").strip() or None
    result: VerseCopilotReturn
    try:
        resolved_osis = osis_value or (
            resolve_passage_reference(passage_value) if passage_value else None
        )
    except PassageResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not resolved_osis:
        raise HTTPException(status_code=422, detail="Provide an OSIS reference or passage.")
    try:
        with trail_service.start_trail(
            workflow="verse_copilot",
            plan_md=VERSE_COPILOT_PLAN,
            mode="verse_copilot",
            input_payload=payload.model_dump(mode="json"),
            user_id=(
                payload.recorder_metadata.user_id
                if payload.recorder_metadata
                else None
            ),
        ) as recorder:
            response = generate_verse_brief(
                session,
                osis=resolved_osis,
                question=payload.question,
                filters=payload.filters,
                model_name=payload.model,
                recorder=recorder,
            )
            recorder.finalize(final_md=response.answer.summary, output_payload=response)
            result = response
    except GuardrailError as exc:
        result = guardrail_http_exception(
            exc,
            session=session,
            question=payload.question,
            osis=resolved_osis,
            filters=payload.filters,
        )
    return result


@router.post(
    "/sermon-prep",
    response_model=SermonPrepResponse,
    response_model_exclude_none=True,
)
def sermon_prep(
    payload: SermonPrepRequest,
    session: Session = Depends(get_session),
) -> SermonPrepReturn:
    trail_service = TrailService(session)
    result: SermonPrepReturn
    try:
        with trail_service.start_trail(
            workflow="sermon_prep",
            plan_md=SERMON_PREP_PLAN,
            mode="sermon_prep",
            input_payload=payload.model_dump(mode="json"),
            user_id=(
                payload.recorder_metadata.user_id
                if payload.recorder_metadata
                else None
            ),
        ) as recorder:
            response = generate_sermon_prep_outline(
                session,
                topic=payload.topic,
                osis=payload.osis,
                filters=payload.filters,
                model_name=payload.model,
                recorder=recorder,
                outline_template=payload.outline_template,
                key_points_limit=payload.key_points_limit,
            )
            recorder.finalize(final_md=response.answer.summary, output_payload=response)
            result = response
    except GuardrailError as exc:
        result = guardrail_http_exception(
            exc,
            session=session,
            question=None,
            osis=payload.osis,
            filters=payload.filters,
        )
    return result


@router.post(
    "/devotional",
    response_model=DevotionalResponse,
    response_model_exclude_none=True,
)
def devotional_flow(
    payload: DevotionalRequest,
    session: Session = Depends(get_session),
) -> DevotionalReturn:
    trail_service = TrailService(session)
    result: DevotionalReturn
    try:
        with trail_service.start_trail(
            workflow="devotional",
            plan_md=DEVOTIONAL_PLAN,
            mode="devotional",
            input_payload=payload.model_dump(mode="json"),
            user_id=None,
        ) as recorder:
            response = generate_devotional_flow(
                session,
                osis=payload.osis,
                focus=payload.focus,
                model_name=payload.model,
                recorder=recorder,
            )
            recorder.finalize(
                final_md=response.reflection,
                output_payload=response,
            )
            result = response
    except GuardrailError as exc:
        result = guardrail_http_exception(
            exc,
            session=session,
            question=payload.focus,
            osis=payload.osis,
            filters=None,
        )
    return result


@router.post(
    "/collaboration",
    response_model_exclude_none=True,
    responses=_BAD_REQUEST_RESPONSE,
)
def collaboration(
    payload: CollaborationRequest,
    session: Session = Depends(get_session),
) -> CollaborationReturn:
    if not payload.viewpoints:
        raise HTTPException(status_code=400, detail="viewpoints cannot be empty")
    trail_service = TrailService(session)
    result: CollaborationReturn
    try:
        with trail_service.start_trail(
            workflow="research_reconciliation",
            plan_md=COLLABORATION_PLAN,
            mode="collaboration",
            input_payload=payload.model_dump(mode="json"),
            user_id=None,
        ) as recorder:
            response = run_research_reconciliation(
                session,
                thread=payload.thread,
                osis=payload.osis,
                viewpoints=payload.viewpoints,
                model_name=payload.model,
                recorder=recorder,
            )
            recorder.finalize(
                final_md=response.synthesized_view,
                output_payload=response,
            )
            result = response
    except GuardrailError as exc:
        result = guardrail_http_exception(
            exc,
            session=session,
            question="; ".join(payload.viewpoints) if payload.viewpoints else None,
            osis=payload.osis,
            filters=None,
        )
    return result


@router.post(
    "/curation",
    response_model_exclude_none=True,
    responses=_BAD_REQUEST_RESPONSE,
)
def corpus_curation(
    payload: CorpusCurationRequest,
    session: Session = Depends(get_session),
) -> CorpusCurationReport:
    since_dt = None
    if payload.since:
        try:
            since_dt = datetime.fromisoformat(payload.since)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="since must be ISO formatted"
            ) from exc
    trail_service = TrailService(session)
    with trail_service.start_trail(
        workflow="corpus_curation",
        plan_md=CORPUS_CURATION_PLAN,
        mode="corpus_curation",
        input_payload=payload.model_dump(mode="json"),
        user_id=None,
    ) as recorder:
        response = run_corpus_curation(session, since=since_dt, recorder=recorder)
        digest = "\n".join(response.summaries)
        recorder.finalize(final_md=digest or None, output_payload=response)
    return response


@router.post(
    "/comparative",
    response_model_exclude_none=True,
    responses=_BAD_REQUEST_RESPONSE,
)
def comparative_analysis(
    payload: ComparativeAnalysisRequest,
    session: Session = Depends(get_session),
) -> ComparativeReturn:
    if not payload.participants:
        raise HTTPException(status_code=400, detail="participants cannot be empty")
    result: ComparativeReturn
    try:
        result = generate_comparative_analysis(
            session,
            osis=payload.osis,
            participants=payload.participants,
            model_name=payload.model,
        )
    except GuardrailError as exc:
        result = guardrail_http_exception(
            exc,
            session=session,
            question=None,
            osis=payload.osis,
            filters=None,
        )
    return result


@router.post(
    "/multimedia",
    response_model=MultimediaDigestResponse,
    response_model_exclude_none=True,
)
def multimedia_digest(
    payload: MultimediaDigestRequest,
    session: Session = Depends(get_session),
) -> MultimediaReturn:
    trail_service = TrailService(session)
    result: MultimediaReturn
    try:
        with trail_service.start_trail(
            workflow="multimedia_digest",
            plan_md=MULTIMEDIA_PLAN,
            mode="multimedia_digest",
            input_payload=payload.model_dump(mode="json"),
            user_id=None,
        ) as recorder:
            response = generate_multimedia_digest(
                session,
                collection=payload.collection,
                model_name=payload.model,
                recorder=recorder,
            )
            final_md = response.answer.summary or "\n".join(response.highlights)
            recorder.finalize(final_md=final_md, output_payload=response)
            result = response
    except GuardrailError as exc:
        result = guardrail_http_exception(
            exc,
            session=session,
            question=payload.collection,
            osis=None,
            filters=None,
        )
    return result


__all__ = [
    "router",
    "verse_copilot",
    "sermon_prep",
    "devotional_flow",
    "collaboration",
    "corpus_curation",
    "comparative_analysis",
    "multimedia_digest",
]
