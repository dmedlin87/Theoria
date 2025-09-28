"""Authentication helpers for protecting API endpoints."""

from __future__ import annotations

from typing import Any, TypedDict

import jwt
from fastapi import Header, HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param

from .core.settings import get_settings


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


def _authenticate_api_key(key: str) -> Principal:
    settings = get_settings()
    allowed_keys = set(settings.api_keys or [])
    if not allowed_keys:
        _reject_forbidden("API key authentication is not configured")
    if key not in allowed_keys:
        _reject_forbidden("Invalid API key")
    return {"method": "api_key", "subject": key, "token": key}


def _decode_jwt(token: str) -> Principal:
    settings = get_settings()
    if not settings.auth_jwt_secret:
        _reject_forbidden("JWT authentication is not configured")

    try:
        payload = jwt.decode(
            token,
            settings.auth_jwt_secret,
            algorithms=settings.auth_jwt_algorithms or ["HS256"],
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


def require_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    api_key_header: str | None = Header(default=None, alias="X-API-Key"),
) -> Principal:
    """Validate API credentials and attach the resolved principal to the request."""

    settings = get_settings()
    principal: Principal | None = None
    if settings.auth_allow_anonymous and not authorization and not api_key_header:
        principal = {
            "method": "anonymous",
            "subject": None,
            "scopes": [],
            "claims": {},
            "token": "",
        }
        request.state.principal = principal
        return principal
    if api_key_header:
        principal = _authenticate_api_key(api_key_header)
    elif authorization:
        scheme, credentials = get_authorization_scheme_param(authorization)
        if not credentials:
            _reject_unauthorized("Missing bearer token")
        if scheme.lower() != "bearer":
            _reject_unauthorized("Unsupported authorization scheme")
        if credentials.count(".") == 2:
            principal = _decode_jwt(credentials)
        else:
            principal = _authenticate_api_key(credentials)
    else:
        _reject_unauthorized("Missing credentials")

    if principal is None:  # pragma: no cover - defensive
        raise RuntimeError("Failed to resolve principal")

    request.state.principal = principal
    return principal


__all__ = ["Principal", "require_principal"]
