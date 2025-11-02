"""Minimal subset of FastAPI response classes for testing."""

from __future__ import annotations

from typing import Any, Iterable
import json


class Response:
    def __init__(self, content: Any = None, status_code: int = 200, media_type: str | None = None) -> None:
        self.content = content
        self.status_code = status_code
        self.media_type = media_type
        self.headers: dict[str, str] = {}
        if media_type:
            self.headers["content-type"] = media_type

    @property
    def text(self) -> str:
        if isinstance(self.content, bytes):
            try:
                return self.content.decode("utf-8")
            except Exception:
                return str(self.content)
        if isinstance(self.content, (dict, list)) and self.media_type == "application/json":
            try:
                return json.dumps(self.content)
            except Exception:
                return str(self.content)
        return "" if self.content is None else str(self.content)

    def json(self) -> Any:
        if isinstance(self.content, (dict, list)):
            return self.content
        if isinstance(self.content, (bytes, str)):
            try:
                payload = self.content.decode("utf-8") if isinstance(self.content, bytes) else self.content
                return json.loads(payload)
            except Exception:
                # Fall back to raw content if not valid JSON
                return self.content
        return self.content


class JSONResponse(Response):
    def __init__(self, content: Any = None, status_code: int = 200) -> None:
        super().__init__(content=content, status_code=status_code, media_type="application/json")


class PlainTextResponse(Response):
    def __init__(self, content: str = "", status_code: int = 200) -> None:
        super().__init__(content=content, status_code=status_code, media_type="text/plain")


class StreamingResponse(Response):
    def __init__(self, content: Iterable[Any], status_code: int = 200, media_type: str | None = None) -> None:
        super().__init__(content=content, status_code=status_code, media_type=media_type)
