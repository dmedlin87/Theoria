"""Lightweight FastAPI stub to satisfy test imports."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

from . import params, responses, status

__all__ = [
    "FastAPI",
    "HTTPException",
    "Header",
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


class Request(SimpleNamespace):
    """Placeholder request object used for typing in tests."""


class Response(SimpleNamespace):
    """Placeholder response object used for typing in tests."""


def Header(default: Any = None, *, alias: str | None = None) -> params.Header:
    """Return a ``Header`` descriptor compatible with FastAPI's helper."""

    return params.Header(default=default, alias=alias)


class FastAPI:
    """Very small subset of FastAPI used by the test harness."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.routes: list[Any] = []
        self.state = SimpleNamespace()
        self._exception_handlers: dict[type[BaseException], Callable[..., Any]] = {}

    def add_middleware(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - stub
        return None

    def add_exception_handler(self, exc_type: type[BaseException], handler: Callable[..., Any]) -> None:
        self._exception_handlers[exc_type] = handler

    def mount(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - stub
        return None


# Re-export commonly used submodules for compatibility.
status = status
responses = responses
