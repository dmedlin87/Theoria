"""Routes exposing AI-assisted workflows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..ai import (
    build_sermon_deliverable,
    build_transcript_deliverable,
    generate_comparative_analysis,
    generate_devotional_flow,
    generate_multimedia_digest,
    generate_sermon_prep_outline,
    generate_verse_brief,
    run_guarded_chat,
    run_corpus_curation,
    run_research_reconciliation,
)
from ..ai.rag import GuardrailError
from ..ai.registry import LLMModel, LLMRegistry, get_llm_registry, save_llm_registry
from ..ai.trails import TrailService
from ..analytics.topics import (
    TopicDigest,
    generate_topic_digest,
    load_topic_digest,
    store_topic_digest,
    upsert_digest_document,
)
from ..analytics.watchlists import (
    create_watchlist,
    delete_watchlist,
    get_watchlist,
    list_watchlist_events,
    list_watchlists,
    run_watchlist,
    update_watchlist,
)
from ..core.database import get_session
from ..core.settings_store import load_setting, save_setting
from ..models.ai import (
    ChatSessionMessage,
    ChatSessionRequest,
    ChatSessionResponse,
    CollaborationRequest,
    ComparativeAnalysisRequest,
    CorpusCurationRequest,
    DevotionalRequest,
    LLMDefaultRequest,
    LLMModelRequest,
    LLMModelUpdateRequest,
    LLMSettingsResponse,
    MultimediaDigestRequest,
    ProviderSettingsRequest,
    ProviderSettingsResponse,
    SermonPrepRequest,
    TranscriptExportRequest,
    VerseCopilotRequest,
)
from ..models.watchlists import (
    WatchlistCreateRequest,
    WatchlistResponse,
    WatchlistRunResponse,
    WatchlistUpdateRequest,
)

router = APIRouter()
settings_router = APIRouter(prefix="/settings/ai", tags=["ai-settings"])


def _persist_and_respond(
    session: Session, registry: LLMRegistry
) -> LLMSettingsResponse:
    save_llm_registry(session, registry)
    return LLMSettingsResponse(**registry.to_response())


@router.get("/llm", response_model=LLMSettingsResponse)
def list_llm_models(session: Session = Depends(get_session)) -> LLMSettingsResponse:
    registry = get_llm_registry(session)
    return LLMSettingsResponse(**registry.to_response())


@router.post("/llm", response_model=LLMSettingsResponse, response_model_exclude_none=True)
def register_llm_model(
    payload: LLMModelRequest, session: Session = Depends(get_session)
) -> LLMSettingsResponse:
    registry = get_llm_registry(session)
    model = LLMModel(
        name=payload.name,
        provider=payload.provider,
        model=payload.model,
        config=dict(payload.config),
    )
    registry.add_model(model, make_default=payload.make_default)
    return _persist_and_respond(session, registry)


@router.patch(
    "/llm/default", response_model=LLMSettingsResponse, response_model_exclude_none=True
)
def set_default_llm_model(
    payload: LLMDefaultRequest, session: Session = Depends(get_session)
) -> LLMSettingsResponse:
    registry = get_llm_registry(session)
    if payload.name not in registry.models:
        raise HTTPException(status_code=404, detail="Unknown model")
    registry.default_model = payload.name
    return _persist_and_respond(session, registry)


@router.patch(
    "/llm/{name}", response_model=LLMSettingsResponse, response_model_exclude_none=True
)
def update_llm_model(
    name: str, payload: LLMModelUpdateRequest, session: Session = Depends(get_session)
) -> LLMSettingsResponse:
    registry = get_llm_registry(session)
    if name not in registry.models:
        raise HTTPException(status_code=404, detail="Unknown model")
    model = registry.models[name]
    if payload.provider:
        model.provider = payload.provider
    if payload.model:
        model.model = payload.model
    if payload.config is not None:
        for key, value in dict(payload.config).items():
            if value is None:
                model.config.pop(key, None)
            else:
                model.config[key] = value
    if payload.make_default:
        registry.default_model = name
    return _persist_and_respond(session, registry)


@router.delete(
    "/llm/{name}", response_model=LLMSettingsResponse, response_model_exclude_none=True
)
def remove_llm_model(name: str, session: Session = Depends(get_session)) -> LLMSettingsResponse:
    registry = get_llm_registry(session)
    if name not in registry.models:
        raise HTTPException(status_code=404, detail="Unknown model")
    registry.remove_model(name)
    return _persist_and_respond(session, registry)


CHAT_PLAN = "\n".join(
    [
        "- Retrieve supporting passages using hybrid search",
        "- Compose a grounded assistant reply with citations",
        "- Validate guardrails before finalising the turn",
    ]
)


@router.post("/chat", response_model=ChatSessionResponse, response_model_exclude_none=True)
def chat_turn(
    payload: ChatSessionRequest, session: Session = Depends(get_session)
) -> ChatSessionResponse:
    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")
    last_user = next(
        (message for message in reversed(payload.messages) if message.role == "user"),
        None,
    )
    if last_user is None:
        raise HTTPException(status_code=400, detail="missing user message")
    question = last_user.content.strip()
    if not question:
        raise HTTPException(status_code=400, detail="user message cannot be blank")

    session_id = payload.session_id or str(uuid4())
    trail_service = TrailService(session)

    try:
        with trail_service.start_trail(
            workflow="chat",
            plan_md=CHAT_PLAN,
            mode="chat",
            input_payload=payload.model_dump(mode="json"),
            user_id=(
                payload.recorder_metadata.user_id
                if payload.recorder_metadata
                else None
            ),
        ) as recorder:
            answer = run_guarded_chat(
                session,
                question=question,
                osis=payload.osis,
                filters=payload.filters,
                model_name=payload.model,
                recorder=recorder,
            )
            message = ChatSessionMessage(
                role="assistant",
                content=answer.model_output or answer.summary,
            )
            recorder.finalize(
                final_md=answer.summary,
                output_payload={
                    "session_id": session_id,
                    "answer": answer,
                    "message": message,
                },
            )
    except GuardrailError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ChatSessionResponse(session_id=session_id, message=message, answer=answer)


_PROVIDER_SETTINGS_KEY = "ai_providers"
_PROVIDER_FIELDS = {"api_key", "base_url", "default_model", "extra_headers"}


def _load_provider_settings(session: Session) -> dict[str, dict[str, object]]:
    payload = load_setting(session, _PROVIDER_SETTINGS_KEY, default={})
    if not isinstance(payload, dict):
        return {}
    settings: dict[str, dict[str, object]] = {}
    for provider, raw in payload.items():
        if not isinstance(provider, str) or not isinstance(raw, dict):
            continue
        normalized: dict[str, object] = {}
        for key in _PROVIDER_FIELDS:
            if key not in raw:
                continue
            value = raw[key]
            if key == "extra_headers":
                if isinstance(value, dict):
                    normalized[key] = {
                        str(h_key): str(h_value)
                        for h_key, h_value in value.items()
                        if isinstance(h_key, str) and isinstance(h_value, str)
                    }
                continue
            normalized[key] = value
        settings[provider] = normalized
    return settings


def _store_provider_settings(
    session: Session, providers: dict[str, dict[str, object]]
) -> None:
    save_setting(session, _PROVIDER_SETTINGS_KEY, providers)


def _provider_response(
    provider: str, payload: dict[str, object] | None
) -> ProviderSettingsResponse:
    payload = payload or {}
    headers = payload.get("extra_headers")
    normalized_headers: dict[str, str] | None = None
    if isinstance(headers, dict):
        normalized_headers = {
            str(key): str(value)
            for key, value in headers.items()
            if isinstance(key, str) and isinstance(value, str)
        }
    base_url_value = payload.get("base_url")
    default_model_value = payload.get("default_model")
    return ProviderSettingsResponse(
        provider=provider,
        base_url=base_url_value if isinstance(base_url_value, str) else None,
        default_model=(
            default_model_value if isinstance(default_model_value, str) else None
        ),
        extra_headers=normalized_headers,
        has_api_key=bool(payload.get("api_key")),
    )


@settings_router.get(
    "/providers",
    response_model=list[ProviderSettingsResponse],
    response_model_exclude_none=True,
)
def list_providers(session: Session = Depends(get_session)) -> list[ProviderSettingsResponse]:
    providers = _load_provider_settings(session)
    return [
        _provider_response(name, payload)
        for name, payload in sorted(providers.items())
    ]


@settings_router.get(
    "/providers/{provider}",
    response_model=ProviderSettingsResponse,
    response_model_exclude_none=True,
)
def get_provider_settings(
    provider: str, session: Session = Depends(get_session)
) -> ProviderSettingsResponse:
    providers = _load_provider_settings(session)
    payload = providers.get(provider)
    if payload is None:
        raise HTTPException(status_code=404, detail="Provider not configured")
    return _provider_response(provider, payload)


@settings_router.put(
    "/providers/{provider}",
    response_model=ProviderSettingsResponse,
    response_model_exclude_none=True,
)
def upsert_provider_settings(
    provider: str,
    payload: ProviderSettingsRequest,
    session: Session = Depends(get_session),
) -> ProviderSettingsResponse:
    providers = _load_provider_settings(session)
    existing = providers.get(provider, {}).copy()
    update_data = payload.model_dump(exclude_unset=True)
    for field in ("base_url", "default_model"):
        if field in update_data:
            value = update_data[field]
            if value is None:
                existing.pop(field, None)
            elif isinstance(value, str) and value:
                existing[field] = value
            else:
                existing.pop(field, None)
    if "extra_headers" in update_data:
        headers = update_data["extra_headers"]
        if headers is None:
            existing.pop("extra_headers", None)
        elif isinstance(headers, dict):
            existing["extra_headers"] = {
                str(key): str(value)
                for key, value in headers.items()
                if isinstance(key, str) and isinstance(value, str)
            }
    if "api_key" in update_data:
        api_key = update_data["api_key"]
        if api_key is None or (isinstance(api_key, str) and not api_key):
            existing.pop("api_key", None)
        elif isinstance(api_key, str):
            existing["api_key"] = api_key
    providers[provider] = existing
    _store_provider_settings(session, providers)
    return _provider_response(provider, existing)


@settings_router.delete(
    "/providers/{provider}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_provider_settings(
    provider: str, session: Session = Depends(get_session)
) -> Response:
    providers = _load_provider_settings(session)
    if provider in providers:
        providers.pop(provider)
        _store_provider_settings(session, providers)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
            user_id=(
                payload.recorder_metadata.user_id
                if payload.recorder_metadata
                else None
            ),
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
    normalized = format.lower()
    package = build_sermon_deliverable(
        response,
        formats=[normalized],
        filters=payload.filters.model_dump(exclude_none=True),
    )
    asset = package.get_asset(normalized)
    return Response(content=asset.content, media_type=asset.media_type)


@router.post("/transcript/export")
def transcript_export(
    payload: TranscriptExportRequest,
    session: Session = Depends(get_session),
) -> Response:
    normalized = payload.format.lower()
    try:
        package = build_transcript_deliverable(
            session, payload.document_id, formats=[normalized]
        )
    except GuardrailError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    asset = package.get_asset(normalized)
    return Response(content=asset.content, media_type=asset.media_type)


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


@router.get("/digest/watchlists", response_model=list[WatchlistResponse])
def list_user_watchlists(
    user_id: str = Query(..., description="Owning user identifier"),
    session: Session = Depends(get_session),
) -> list[WatchlistResponse]:
    return list_watchlists(session, user_id)


@router.post(
    "/digest/watchlists",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user_watchlist(
    payload: WatchlistCreateRequest, session: Session = Depends(get_session)
) -> WatchlistResponse:
    return create_watchlist(session, payload)


@router.patch(
    "/digest/watchlists/{watchlist_id}", response_model=WatchlistResponse
)
def update_user_watchlist(
    watchlist_id: str,
    payload: WatchlistUpdateRequest,
    session: Session = Depends(get_session),
) -> WatchlistResponse:
    watchlist = get_watchlist(session, watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return update_watchlist(session, watchlist, payload)


@router.delete("/digest/watchlists/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_watchlist(
    watchlist_id: str, session: Session = Depends(get_session)
) -> None:
    watchlist = get_watchlist(session, watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    delete_watchlist(session, watchlist)


@router.get(
    "/digest/watchlists/{watchlist_id}/events",
    response_model=list[WatchlistRunResponse],
)
def list_user_watchlist_events(
    watchlist_id: str,
    since: datetime | None = Query(
        default=None, description="Return events generated after this timestamp"
    ),
    session: Session = Depends(get_session),
) -> list[WatchlistRunResponse]:
    watchlist = get_watchlist(session, watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return list_watchlist_events(session, watchlist, since=since)


@router.get(
    "/digest/watchlists/{watchlist_id}/preview",
    response_model=WatchlistRunResponse,
)
def preview_user_watchlist(
    watchlist_id: str, session: Session = Depends(get_session)
) -> WatchlistRunResponse:
    watchlist = get_watchlist(session, watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return run_watchlist(session, watchlist, persist=False)


@router.post(
    "/digest/watchlists/{watchlist_id}/run",
    response_model=WatchlistRunResponse,
)
def run_user_watchlist(
    watchlist_id: str, session: Session = Depends(get_session)
) -> WatchlistRunResponse:
    watchlist = get_watchlist(session, watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return run_watchlist(session, watchlist, persist=True)


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
