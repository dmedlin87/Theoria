"""Security interfaces exposed to application services."""

from __future__ import annotations

from typing import Any, Awaitable, Protocol, TypedDict, runtime_checkable


class Principal(TypedDict, total=False):
    """Authenticated caller metadata."""

    method: str
    subject: str | None
    scopes: list[str]
    claims: dict[str, Any]
    token: str


@runtime_checkable
class PrincipalResolver(Protocol):
    """Resolve the active principal for a request context."""

    def resolve(
        self,
        *,
        request: Any,
        authorization: str | None,
        api_key_header: str | None,
    ) -> Awaitable[Principal]:
        """Resolve and validate the principal for the given request."""


__all__ = ["Principal", "PrincipalResolver"]

