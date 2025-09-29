"""Shared helpers for serialising API error responses."""

from __future__ import annotations

from typing import Any, Mapping


def build_error_detail(
    message: str, code: str, metadata: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Return a serialisable detail payload for ``HTTPException`` responses."""

    detail: dict[str, Any] = {"message": message, "code": code}
    if metadata:
        detail["metadata"] = dict(metadata)
    return detail
