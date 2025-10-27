"""Application package initialisation with compatibility shims."""

from __future__ import annotations

from fastapi import status as fastapi_status

try:  # pragma: no cover - defensive import for environments without Starlette
    from starlette import status as starlette_status
except ImportError:  # pragma: no cover - fallback if Starlette is absent
    starlette_status = fastapi_status  # type: ignore[assignment]

# FastAPI 0.115 (Starlette >=0.40) renamed HTTP_422_UNPROCESSABLE_CONTENT to
# HTTP_422_UNPROCESSABLE_ENTITY. Maintain the previous attribute for the rest of
# the codebase and historical clients until we can migrate fully.
_unprocessable = getattr(
    fastapi_status,
    "HTTP_422_UNPROCESSABLE_ENTITY",
    422,  # pragma: no cover - ultra defensive default
)

if not hasattr(fastapi_status, "HTTP_422_UNPROCESSABLE_CONTENT"):
    setattr(fastapi_status, "HTTP_422_UNPROCESSABLE_CONTENT", _unprocessable)

if not hasattr(starlette_status, "HTTP_422_UNPROCESSABLE_CONTENT"):
    setattr(starlette_status, "HTTP_422_UNPROCESSABLE_CONTENT", _unprocessable)

__all__ = ["fastapi_status"]
