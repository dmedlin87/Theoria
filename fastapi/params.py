"""Stub implementations for FastAPI parameter helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Header:
    default: Any = None
    alias: str | None = None

    def __iter__(self):  # pragma: no cover - compatibility hook
        yield self.default
        yield self.alias
