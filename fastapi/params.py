"""Stub implementations for FastAPI parameter helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Header:
    default: Any = None
    alias: str | None = None

    def __iter__(self):  # pragma: no cover - compatibility hook
        yield self.default
        yield self.alias


@dataclass
class Depends:
    dependency: Callable[..., Any] | None = None
    use_cache: bool = True


@dataclass
class Query:
    default: Any = None
    alias: str | None = None
    description: str | None = None
    gt: float | None = None
    lt: float | None = None
    ge: float | None = None
    le: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    regex: str | None = None
