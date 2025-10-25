"""Theo Engine FastAPI application entrypoint."""

from __future__ import annotations

import inspect
import os
from functools import wraps

from .bootstrap import ROUTER_REGISTRATIONS, create_app
from .bootstrap.lifecycle import lifespan


def _should_patch_httpx() -> bool:
    disabled = os.getenv("THEO_DISABLE_HTTPX_COMPAT_PATCH", "0").lower()
    if disabled in {"1", "true", "yes"}:
        return False
    return True


def _patch_httpx_testclient_compat() -> None:
    try:
        import httpx  # type: ignore[import]
    except Exception:  # pragma: no cover - optional dependency
        return
    try:
        client_signature = inspect.signature(httpx.Client.__init__)
    except (AttributeError, ValueError):
        return
    if "app" in client_signature.parameters:
        return
    transport_cls = getattr(httpx, "ASGITransport", None)
    if transport_cls is None:
        return
    original_client_init = httpx.Client.__init__
    if getattr(original_client_init, "__theo_patched__", False):
        return

    @wraps(original_client_init)
    def compat_client_init(self, *args, app=None, transport=None, **kwargs):
        if app is not None and transport is None:
            transport = transport_cls(app=app)
        return original_client_init(self, *args, transport=transport, **kwargs)

    compat_client_init.__theo_patched__ = True  # type: ignore[attr-defined]
    httpx.Client.__init__ = compat_client_init  # type: ignore[assignment]

    async_client_cls = getattr(httpx, "AsyncClient", None)
    if async_client_cls is None:
        return
    original_async_init = async_client_cls.__init__
    try:
        async_signature = inspect.signature(original_async_init)
    except (AttributeError, ValueError):
        return
    if "app" in async_signature.parameters:
        return

    @wraps(original_async_init)
    def compat_async_init(self, *args, app=None, transport=None, **kwargs):
        if app is not None and transport is None:
            transport = transport_cls(app=app)
        return original_async_init(self, *args, transport=transport, **kwargs)

    compat_async_init.__theo_patched__ = True  # type: ignore[attr-defined]
    async_client_cls.__init__ = compat_async_init  # type: ignore[assignment]


if _should_patch_httpx():
    _patch_httpx_testclient_compat()

app = create_app()

__all__ = ["app", "create_app", "ROUTER_REGISTRATIONS", "lifespan"]
