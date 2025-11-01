"""Minimal subset of FastAPI response classes for testing."""

from __future__ import annotations

from typing import Any, Iterable


class Response:
    def __init__(self, content: Any = None, status_code: int = 200, media_type: str | None = None) -> None:
        self.content = content
        self.status_code = status_code
        self.media_type = media_type


class JSONResponse(Response):
    def __init__(self, content: Any = None, status_code: int = 200) -> None:
        super().__init__(content=content, status_code=status_code, media_type="application/json")


class PlainTextResponse(Response):
    def __init__(self, content: str = "", status_code: int = 200) -> None:
        super().__init__(content=content, status_code=status_code, media_type="text/plain")


class StreamingResponse(Response):
    def __init__(self, content: Iterable[Any], status_code: int = 200, media_type: str | None = None) -> None:
        super().__init__(content=content, status_code=status_code, media_type=media_type)
