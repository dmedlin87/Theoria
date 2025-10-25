"""Facade for resolving principals within the application."""

from __future__ import annotations

from typing import Any

from ..security import Principal, PrincipalResolver

_resolver: PrincipalResolver | None = None


def set_principal_resolver(resolver: PrincipalResolver) -> None:
    """Register the resolver used for authentication."""

    global _resolver
    _resolver = resolver


def get_principal_resolver() -> PrincipalResolver:
    """Return the active principal resolver."""

    if _resolver is None:
        raise RuntimeError("Principal resolver has not been configured")
    return _resolver


async def resolve_principal(*, request: Any, authorization: str | None, api_key_header: str | None) -> Principal:
    """Resolve the current principal using the configured resolver."""

    resolver = get_principal_resolver()
    return await resolver.resolve(
        request=request,
        authorization=authorization,
        api_key_header=api_key_header,
    )


__all__ = ["Principal", "get_principal_resolver", "resolve_principal", "set_principal_resolver"]

