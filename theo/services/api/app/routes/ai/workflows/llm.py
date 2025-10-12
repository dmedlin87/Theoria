"""LLM registry management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from theo.services.api.app.ai.registry import (
    LLMModel,
    LLMRegistry,
    get_llm_registry,
    save_llm_registry,
)
from theo.application.facades.database import get_session
from theo.services.api.app.models.ai import (
    LLMDefaultRequest,
    LLMModelRequest,
    LLMModelUpdateRequest,
    LLMSettingsResponse,
)

router = APIRouter()


def _persist_and_respond(session: Session, registry: LLMRegistry) -> LLMSettingsResponse:
    save_llm_registry(session, registry)
    return LLMSettingsResponse(**registry.to_response())


@router.get("/llm", response_model=LLMSettingsResponse)
def list_llm_models(session: Session = Depends(get_session)) -> LLMSettingsResponse:
    registry = get_llm_registry(session)
    return LLMSettingsResponse(**registry.to_response())


@router.post(
    "/llm",
    response_model=LLMSettingsResponse,
    response_model_exclude_none=True,
)
def register_llm_model(
    payload: LLMModelRequest, session: Session = Depends(get_session)
) -> LLMSettingsResponse:
    registry = get_llm_registry(session)
    model = LLMModel(
        name=payload.name,
        provider=payload.provider,
        model=payload.model,
        config=dict(payload.config),
        pricing=dict(payload.pricing),
        latency=dict(payload.latency),
        routing=dict(payload.routing),
    )
    registry.add_model(model, make_default=payload.make_default)
    return _persist_and_respond(session, registry)


@router.patch(
    "/llm/default",
    response_model=LLMSettingsResponse,
    response_model_exclude_none=True,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Resource not found"}},
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
    "/llm/{name}",
    response_model=LLMSettingsResponse,
    response_model_exclude_none=True,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Resource not found"}},
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
    if payload.pricing is not None:
        for key, value in dict(payload.pricing).items():
            if value is None:
                model.pricing.pop(key, None)
            else:
                model.pricing[key] = value
    if payload.latency is not None:
        for key, value in dict(payload.latency).items():
            if value is None:
                model.latency.pop(key, None)
            else:
                model.latency[key] = value
    if payload.routing is not None:
        for key, value in dict(payload.routing).items():
            if value is None:
                model.routing.pop(key, None)
            else:
                model.routing[key] = value
    if payload.make_default:
        registry.default_model = name
    return _persist_and_respond(session, registry)


@router.delete(
    "/llm/{name}",
    response_model=LLMSettingsResponse,
    response_model_exclude_none=True,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Resource not found"}},
)
def remove_llm_model(name: str, session: Session = Depends(get_session)) -> LLMSettingsResponse:
    registry = get_llm_registry(session)
    if name not in registry.models:
        raise HTTPException(status_code=404, detail="Unknown model")
    registry.remove_model(name)
    return _persist_and_respond(session, registry)


__all__ = [
    "router",
    "list_llm_models",
    "register_llm_model",
    "set_default_llm_model",
    "update_llm_model",
    "remove_llm_model",
]
