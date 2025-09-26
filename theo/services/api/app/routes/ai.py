"""Routes exposing AI-assisted workflows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..ai import (
    build_sermon_prep_package,
    build_transcript_package,
    generate_comparative_analysis,
    generate_devotional_flow,
    generate_multimedia_digest,
    generate_sermon_prep_outline,
    generate_verse_brief,
    run_corpus_curation,
    run_research_reconciliation,
)
from ..ai.rag import GuardrailError
from ..ai.registry import LLMModel, get_llm_registry, save_llm_registry
from ..ai.trails import TrailService
from ..analytics.topics import (
    TopicDigest,
    generate_topic_digest,
    load_topic_digest,
    store_topic_digest,
    upsert_digest_document,
)
from ..core.database import get_session
from ..models.ai import (
    CollaborationRequest,
    ComparativeAnalysisRequest,
    CorpusCurationRequest,
    DevotionalRequest,
    LLMModelRequest,
    LLMSettingsResponse,
    MultimediaDigestRequest,
    SermonPrepRequest,
    TranscriptExportRequest,
    VerseCopilotRequest,
)

router = APIRouter()

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


@router.post("/verse", response_model_exclude_none=True)
def verse_copilot(
    payload: VerseCopilotRequest,
    session: Session = Depends(get_session),
):
    trail_service = TrailService(session)
    try:
        with trail_service.start_trail(
            workflow="verse_copilot",
            plan_md=VERSE_COPILOT_PLAN,
            mode="verse_copilot",
            input_payload=payload.model_dump(mode="json"),
        ) as recorder:
            response = generate_verse_brief(
                session,
                osis=payload.osis,
                question=payload.question,
                filters=payload.filters,
                model_name=payload.model,
                recorder=recorder,
            )
            recorder.finalize(final_md=response.answer.summary, output_payload=response)
            return response
    except GuardrailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sermon-prep", response_model_exclude_none=True)
def sermon_prep(
    payload: SermonPrepRequest,
    session: Session = Depends(get_session),
):
    trail_service = TrailService(session)
    try:
        with trail_service.start_trail(
            workflow="sermon_prep",
            plan_md=SERMON_PREP_PLAN,
            mode="sermon_prep",
            input_payload=payload.model_dump(mode="json"),
        ) as recorder:
            response = generate_sermon_prep_outline(
                session,
                topic=payload.topic,
                osis=payload.osis,
                filters=payload.filters,
                model_name=payload.model,
                recorder=recorder,
            )
            recorder.finalize(final_md=response.answer.summary, output_payload=response)
            return response
    except GuardrailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sermon-prep/export")
def sermon_prep_export(
    payload: SermonPrepRequest,
    format: str = Query(default="markdown", description="markdown, ndjson, or csv"),
    session: Session = Depends(get_session),
) -> Response:
    try:
        response = generate_sermon_prep_outline(
            session,
            topic=payload.topic,
            osis=payload.osis,
            filters=payload.filters,
            model_name=payload.model,
        )
    except GuardrailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    body, media_type = build_sermon_prep_package(response, format=format.lower())
    return Response(content=body, media_type=media_type)


@router.post("/transcript/export")
def transcript_export(
    payload: TranscriptExportRequest,
    session: Session = Depends(get_session),
) -> Response:
    normalized = payload.format.lower()
    try:
        body, media_type = build_transcript_package(
            session, payload.document_id, format=normalized
        )
    except GuardrailError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(content=body, media_type=media_type)


@router.post("/comparative", response_model_exclude_none=True)
def comparative_analysis(
    payload: ComparativeAnalysisRequest,
    session: Session = Depends(get_session),
):
    if not payload.participants:
        raise HTTPException(status_code=400, detail="participants cannot be empty")
    try:
        return generate_comparative_analysis(
            session,
            osis=payload.osis,
            participants=payload.participants,
            model_name=payload.model,
        )
    except GuardrailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/multimedia", response_model_exclude_none=True)
def multimedia_digest(
    payload: MultimediaDigestRequest,
    session: Session = Depends(get_session),
):
    try:
        return generate_multimedia_digest(
            session,
            collection=payload.collection,
            model_name=payload.model,
        )
    except GuardrailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/devotional", response_model_exclude_none=True)
def devotional_flow(
    payload: DevotionalRequest,
    session: Session = Depends(get_session),
):
    try:
        return generate_devotional_flow(
            session,
            osis=payload.osis,
            focus=payload.focus,
            model_name=payload.model,
        )
    except GuardrailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/collaboration", response_model_exclude_none=True)
def collaboration(
    payload: CollaborationRequest,
    session: Session = Depends(get_session),
):
    if not payload.viewpoints:
        raise HTTPException(status_code=400, detail="viewpoints cannot be empty")
    try:
        return run_research_reconciliation(
            session,
            thread=payload.thread,
            osis=payload.osis,
            viewpoints=payload.viewpoints,
            model_name=payload.model,
        )
    except GuardrailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/curation", response_model_exclude_none=True)
def corpus_curation(
    payload: CorpusCurationRequest,
    session: Session = Depends(get_session),
):
    since_dt = None
    if payload.since:
        try:
            since_dt = datetime.fromisoformat(payload.since)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="since must be ISO formatted"
            ) from exc
    return run_corpus_curation(session, since=since_dt)


@router.get(
    "/digest", response_model=TopicDigest | None, response_model_exclude_none=True
)
def get_topic_digest(session: Session = Depends(get_session)):
    digest = load_topic_digest(session)
    if digest is None:
        digest = generate_topic_digest(session)
        upsert_digest_document(session, digest)
        store_topic_digest(session, digest)
    return digest


@router.post("/digest", response_model=TopicDigest)
def refresh_topic_digest(
    hours: int = Query(default=168, ge=1, description="Lookback window in hours"),
    session: Session = Depends(get_session),
):
    since = datetime.now(UTC) - timedelta(hours=hours)
    digest = generate_topic_digest(session, since)
    upsert_digest_document(session, digest)
    store_topic_digest(session, digest)
    return digest


@router.get("/llm", response_model=LLMSettingsResponse)
def list_models(session: Session = Depends(get_session)) -> LLMSettingsResponse:
    registry = get_llm_registry(session)
    return LLMSettingsResponse(**registry.to_response())


@router.post("/llm", response_model=LLMSettingsResponse)
def add_model(
    payload: LLMModelRequest,
    session: Session = Depends(get_session),
) -> LLMSettingsResponse:
    registry = get_llm_registry(session)
    registry.add_model(
        LLMModel(
            name=payload.name,
            provider=payload.provider,
            model=payload.model,
            config=dict(payload.config),
        ),
        make_default=payload.make_default,
    )
    save_llm_registry(session, registry)
    return LLMSettingsResponse(**registry.to_response())


@router.delete("/llm/{name}", response_model=LLMSettingsResponse)
def remove_model(
    name: str, session: Session = Depends(get_session)
) -> LLMSettingsResponse:
    registry = get_llm_registry(session)
    registry.remove_model(name)
    save_llm_registry(session, registry)
    return LLMSettingsResponse(**registry.to_response())
