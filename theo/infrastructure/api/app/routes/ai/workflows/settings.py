"""Provider configuration routes for AI workflows."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from theo.application.facades.database import get_session
from theo.application.facades.settings_store import load_setting, save_setting
from theo.infrastructure.api.app.models.ai import (
    ProviderSettingsRequest,
    ProviderSettingsResponse,
)

from ....errors import AIWorkflowError

router = APIRouter(prefix="/settings/ai", tags=["ai-settings"])

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


@router.get(
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


@router.get(
    "/providers/{provider}",
    response_model=ProviderSettingsResponse,
    response_model_exclude_none=True,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Resource not found"}},
)
def get_provider_settings(
    provider: str, session: Session = Depends(get_session)
) -> ProviderSettingsResponse:
    providers = _load_provider_settings(session)
    payload = providers.get(provider)
    if payload is None:
        raise AIWorkflowError(
            "Provider not configured",
            code="AI_PROVIDER_NOT_CONFIGURED",
            status_code=status.HTTP_404_NOT_FOUND,
            data={"provider": provider},
        )
    return _provider_response(provider, payload)


@router.put(
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


@router.delete(
    "/providers/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_provider_settings(
    provider: str, session: Session = Depends(get_session)
) -> Response:
    providers = _load_provider_settings(session)
    if provider in providers:
        providers.pop(provider)
        _store_provider_settings(session, providers)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = [
    "router",
    "list_providers",
    "get_provider_settings",
    "upsert_provider_settings",
    "delete_provider_settings",
]
