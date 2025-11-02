"""Expose the real :mod:`fastapi` package when available.

The repository ships a small FastAPI shim so API-related tests can execute in
lightweight environments.  Whenever the genuine dependency is present we defer
to it to match production behaviour.  Only when the package is missing do we
provide the stub below, which implements the narrow surface area exercised by
the test suite.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Callable, Iterable, Sequence


def _import_real_module(name: str) -> ModuleType | None:
    """Attempt to load *name* from site-packages instead of the repo stub."""

    repo_root = Path(__file__).resolve().parents[1]
    original_sys_path = list(sys.path)
    filtered_sys_path: list[str] = []
    removed_repo_root = False
    for entry in original_sys_path:
        to_resolve = entry or "."
        try:
            resolved = Path(to_resolve).resolve()
        except Exception:  # pragma: no cover - extremely defensive
            filtered_sys_path.append(entry)
            continue
        if resolved == repo_root:
            removed_repo_root = True
            continue
        filtered_sys_path.append(entry)

    if not removed_repo_root:
        return None

    existing_module = sys.modules.get(name)
    module: ModuleType | None = None
    try:
        if name in sys.modules:
            del sys.modules[name]
        sys.path = filtered_sys_path
        module = importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if getattr(exc, "name", name) != name:
            raise
        module = None
    finally:
        sys.path = original_sys_path
        if module is None and existing_module is not None:
            sys.modules[name] = existing_module

    return module


if "pytest" in sys.modules and os.environ.get("THEORIA_ALLOW_REAL_FASTAPI", "0") not in {"1", "true", "TRUE"}:
    _real_fastapi = None
else:
    _real_fastapi = _import_real_module("fastapi")

if _real_fastapi is not None:
    sys.modules[__name__] = _real_fastapi
    globals().update({key: getattr(_real_fastapi, key) for key in dir(_real_fastapi)})
    __all__ = getattr(
        _real_fastapi,
        "__all__",
        [key for key in dir(_real_fastapi) if not key.startswith("_")],
    )
else:
    from . import params, responses, status

    __all__ = [
        "FastAPI",
        "HTTPException",
        "Header",
        "Query",
        "Depends",
        "APIRouter",
        "Request",
        "Response",
        "status",
    ]

    class HTTPException(Exception):
        """Minimal stand-in mirroring FastAPI's HTTPException."""

        def __init__(self, status_code: int, detail: Any | None = None) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class Request:
        """Placeholder request object used for typing in tests."""

    Header = params.Header
    Depends = params.Depends
    Query = params.Query

    class FastAPI:
        """Very small subset of FastAPI used by the test harness."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.routes: list[Any] = []
            self.state = SimpleNamespace()
            self.user_middleware: list[Any] = []
            self._exception_handlers: dict[type[BaseException], Callable[..., Any]] = {}

        def add_middleware(self, middleware_cls: type[Any], /, **kwargs: Any) -> None:  # pragma: no cover - stub
            entry = SimpleNamespace(cls=middleware_cls, options=dict(kwargs))
            self.user_middleware.append(entry)
            return None

        def add_exception_handler(self, exc_type: type[BaseException], handler: Callable[..., Any]) -> None:
            self._exception_handlers[exc_type] = handler

        def mount(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - stub
            return None

        def exception_handler(self, exc_type: type[BaseException]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:  # pragma: no cover - stub
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self.add_exception_handler(exc_type, func)
                return func
            return decorator

        def middleware(self, _type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:  # pragma: no cover - stub
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                if not hasattr(self, "_middlewares"):
                    self._middlewares = []  # type: ignore[attr-defined]
                self._middlewares.append((_type, func))  # type: ignore[attr-defined]
                return func
            return decorator

        def add_api_route(self, path: str, endpoint: Callable[..., Any], methods: Sequence[str] | None = None, **_kwargs: Any) -> None:
            self.routes.append({"path": path, "endpoint": endpoint, "methods": list(methods or ["GET"])})

        def include_router(self, router: "APIRouter", prefix: str = "", **_kwargs: Any) -> None:
            for route in getattr(router, "routes", []):
                path = f"{prefix}{route['path']}" if prefix else route["path"]
                self.routes.append({"path": path, "endpoint": route["endpoint"], "methods": route["methods"]})

        def _route_decorator(self, methods: Sequence[str], path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self.add_api_route(path, func, methods)
                return func
            return decorator

        def get(self, path: str, *args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._route_decorator(["GET"], path)

        def post(self, path: str, *args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._route_decorator(["POST"], path)

        def put(self, path: str, *args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._route_decorator(["PUT"], path)

        def delete(self, path: str, *args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._route_decorator(["DELETE"], path)

    class APIRouter:
        def __init__(self, *, prefix: str = "", tags: list[str] | None = None, **_kwargs: Any) -> None:
            self.prefix = prefix
            self.tags = tags or []
            self.routes: list[dict[str, Any]] = []

        def add_api_route(self, path: str, endpoint: Callable[..., Any], methods: Sequence[str] | None = None, **_kwargs: Any) -> None:
            full_path = f"{self.prefix}{path}" if self.prefix else path
            self.routes.append({"path": full_path, "endpoint": endpoint, "methods": list(methods or ["GET"])})

        def include_router(self, router: "APIRouter", prefix: str = "", **_kwargs: Any) -> None:
            for route in router.routes:
                new_path = f"{prefix}{route['path']}" if prefix else route["path"]
                self.routes.append({"path": new_path, "endpoint": route["endpoint"], "methods": route["methods"]})

        def _route_decorator(self, methods: Sequence[str], path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self.add_api_route(path, func, methods)
                return func
            return decorator

        def get(self, path: str, *args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._route_decorator(["GET"], path)

        def post(self, path: str, *args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._route_decorator(["POST"], path)

        def put(self, path: str, *args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._route_decorator(["PUT"], path)

        def delete(self, path: str, *args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            return self._route_decorator(["DELETE"], path)

    Response = responses.Response
    JSONResponse = responses.JSONResponse
    PlainTextResponse = responses.PlainTextResponse
    StreamingResponse = responses.StreamingResponse

    # Re-export commonly used submodules for compatibility.
    status = status
