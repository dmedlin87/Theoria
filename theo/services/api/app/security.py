"""Authentication helpers for protecting API endpoints."""

from __future__ import annotations

from typing import Any, TypedDict

import jwt
from fastapi import Header, HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param

from .core.settings import Settings, get_settings


class Principal(TypedDict, total=False):
    """Authenticated caller metadata stored on the request state."""

    method: str
    subject: str | None
    scopes: list[str]
    claims: dict[str, Any]
    token: str


def _reject_unauthorized(detail: str) -> None:
    raise HTTPException(  # pragma: no cover - helper for readability
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _reject_forbidden(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _authenticate_api_key(key: str, settings: Settings) -> Principal:
    allowed_keys = set(settings.api_keys or [])
    if not allowed_keys:
        _reject_forbidden("API key authentication is not configured")
    if key not in allowed_keys:
        _reject_forbidden("Invalid API key")
    return {"method": "api_key", "subject": key, "token": key}


def _decode_jwt(token: str, settings: Settings) -> Principal:
    if not settings.has_auth_jwt_credentials():
        _reject_forbidden("JWT authentication is not configured")

    algorithms = settings.auth_jwt_algorithms or ["HS256"]

    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if not algorithm:
            raise jwt.InvalidTokenError("Missing signing algorithm")
        if algorithm not in algorithms:
            raise jwt.InvalidTokenError("Unsupported signing algorithm")
        verification_key: str | None
        if algorithm.startswith("HS"):
            verification_key = settings.auth_jwt_secret
        elif algorithm.startswith("RS"):
            verification_key = settings.load_auth_jwt_public_key()
        else:
            verification_key = settings.auth_jwt_secret or settings.load_auth_jwt_public_key()
        if not verification_key:
            _reject_forbidden("JWT authentication is not configured")
        payload = jwt.decode(
            token,
            verification_key,
            algorithms=[algorithm],
            audience=settings.auth_jwt_audience,
            issuer=settings.auth_jwt_issuer,
        )
        subject = payload.get("sub")
        scopes = payload.get("scopes")
        if isinstance(scopes, str):
            scopes = [scope.strip() for scope in scopes.split() if scope.strip()]
        elif not isinstance(scopes, list):
            scopes = []
        return {
            "method": "jwt",
            "subject": subject,
            "scopes": scopes,
            "claims": payload,
            "token": token,
        }
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid bearer token",
        ) from exc


def _anonymous_principal() -> Principal:
    return {
        "method": "anonymous",
        "subject": None,
        "scopes": [],
        "claims": {},
        "token": "",
    }


def _auth_configured(settings: Settings) -> bool:
    return bool(settings.api_keys or settings.has_auth_jwt_credentials())


def _principal_from_authorization(authorization: str, settings: Settings) -> Principal:
    scheme, credentials = get_authorization_scheme_param(authorization)
    if not credentials:
        _reject_unauthorized("Missing bearer token")
    if scheme.lower() != "bearer":
        _reject_unauthorized("Unsupported authorization scheme")
    if credentials.count(".") == 2:
        return _decode_jwt(credentials, settings)
    return _authenticate_api_key(credentials, settings)


def _principal_from_headers(
    authorization: str | None, api_key_header: str | None, settings: Settings
) -> Principal:
    if api_key_header:
        return _authenticate_api_key(api_key_header, settings)
    if authorization:
        return _principal_from_authorization(authorization, settings)
    _reject_unauthorized("Missing credentials")


def _resolve_settings_with_credentials() -> tuple[Settings, bool]:
    settings = get_settings()
    credentials_configured = _auth_configured(settings)
    if credentials_configured:
        return settings, credentials_configured

    # Tests (and some local tooling) mutate environment variables at runtime to
    # toggle authentication strategies. When this happens between requests we may
    # still be holding on to a cached ``Settings`` instance without the refreshed
    # credentials. Attempt a single cache refresh before treating the
    # configuration as missing so we honour the latest environment changes.
    get_settings.cache_clear()
    settings = get_settings()
    return settings, _auth_configured(settings)


def require_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    api_key_header: str | None = Header(default=None, alias="X-API-Key"),
) -> Principal:
    """Validate API credentials and attach the resolved principal to the request."""

    settings, credentials_configured = _resolve_settings_with_credentials()

    allow_anonymous = settings.auth_allow_anonymous and not credentials_configured

    if not credentials_configured:
        if not allow_anonymous:
            _reject_forbidden("Authentication is not configured")
        if not authorization and not api_key_header:
            principal = _anonymous_principal()
            request.state.principal = principal
            return principal

    if allow_anonymous and not authorization and not api_key_header:
        principal = _anonymous_principal()
        request.state.principal = principal
        return principal

    principal = _principal_from_headers(authorization, api_key_header, settings)

    request.state.principal = principal
    return principal


__all__ = ["Principal", "require_principal"]
