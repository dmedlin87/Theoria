"""FastAPI-backed principal resolver implementation."""

from __future__ import annotations

import threading
import time
from typing import Any

import jwt
from fastapi import Header, HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param

from theo.application.facades.security import resolve_principal, set_principal_resolver
from theo.application.facades.settings import Settings, get_settings
from theo.application.security import Principal, PrincipalResolver


class FastAPIPrincipalResolver(PrincipalResolver):
    """Resolve principals using FastAPI request context and Theo settings."""

    def __init__(self) -> None:
        self._settings_refresh_lock = threading.Lock()
        self._settings_refreshed_at: float | None = None
        self._settings_refresh_interval_seconds = 5.0

    async def resolve(
        self,
        *,
        request: Request,
        authorization: str | None,
        api_key_header: str | None,
    ) -> Principal:
        settings, credentials_configured = self._resolve_settings_with_credentials()

        allow_anonymous = settings.auth_allow_anonymous and not credentials_configured

        if not credentials_configured:
            if not allow_anonymous:
                self._reject_forbidden("Authentication is not configured")
            if not authorization and not api_key_header:
                principal = self._anonymous_principal()
                request.state.principal = principal
                return principal

        if allow_anonymous and not authorization and not api_key_header:
            principal = self._anonymous_principal()
            request.state.principal = principal
            return principal

        principal = self._principal_from_headers(authorization, api_key_header, settings)
        request.state.principal = principal
        return principal

    # Internal helpers -----------------------------------------------------------

    def _resolve_settings_with_credentials(self) -> tuple[Settings, bool]:
        settings = get_settings()
        credentials_configured = self._auth_configured(settings)
        if credentials_configured:
            return settings, credentials_configured

        self._refresh_settings_cache_if_stale()
        refreshed_settings = get_settings()
        return refreshed_settings, self._auth_configured(refreshed_settings)

    def _refresh_settings_cache_if_stale(self) -> None:
        now = time.monotonic()
        with self._settings_refresh_lock:
            if (
                self._settings_refreshed_at is not None
                and now - self._settings_refreshed_at < self._settings_refresh_interval_seconds
            ):
                return
            get_settings.cache_clear()
            self._settings_refreshed_at = now

    def _auth_configured(self, settings: Settings) -> bool:
        return bool(settings.api_keys or settings.has_auth_jwt_credentials())

    def _principal_from_headers(
        self, authorization: str | None, api_key_header: str | None, settings: Settings
    ) -> Principal:
        if api_key_header:
            return self._authenticate_api_key(api_key_header, settings)
        if authorization:
            return self._principal_from_authorization(authorization, settings)
        self._reject_unauthorized("Missing credentials")

    def _principal_from_authorization(self, authorization: str, settings: Settings) -> Principal:
        scheme, credentials = get_authorization_scheme_param(authorization)
        if not credentials:
            self._reject_unauthorized("Missing bearer token")
        if scheme.lower() != "bearer":
            self._reject_unauthorized("Unsupported authorization scheme")
        if credentials.count(".") == 2:
            return self._decode_jwt(credentials, settings)
        return self._authenticate_api_key(credentials, settings)

    def _authenticate_api_key(self, key: str, settings: Settings) -> Principal:
        allowed_keys = set(settings.api_keys or [])
        if not allowed_keys:
            self._reject_forbidden("API key authentication is not configured")
        if key not in allowed_keys:
            self._reject_forbidden("Invalid API key")
        return {"method": "api_key", "subject": key, "token": key}

    def _decode_jwt(self, token: str, settings: Settings) -> Principal:
        if not settings.has_auth_jwt_credentials():
            self._reject_forbidden("JWT authentication is not configured")

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
                self._reject_forbidden("JWT authentication is not configured")
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
        except jwt.ExpiredSignatureError as exc:  # pragma: no cover - optional path
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

    def _anonymous_principal(self) -> Principal:
        return {
            "method": "anonymous",
            "subject": None,
            "scopes": [],
            "claims": {},
            "token": "",
        }

    @staticmethod
    def _reject_unauthorized(detail: str) -> None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

    @staticmethod
    def _reject_forbidden(detail: str) -> None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


async def require_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    api_key_header: str | None = Header(default=None, alias="X-API-Key"),
) -> Principal:
    """FastAPI dependency that resolves the current principal."""

    return await resolve_principal(
        request=request,
        authorization=authorization,
        api_key_header=api_key_header,
    )


def configure_principal_resolver() -> None:
    """Register the FastAPI resolver with the application facade."""

    set_principal_resolver(FastAPIPrincipalResolver())


__all__ = ["FastAPIPrincipalResolver", "configure_principal_resolver", "require_principal"]

