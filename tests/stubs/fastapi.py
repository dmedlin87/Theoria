"""Minimal FastAPI stub for CLI tests."""

from __future__ import annotations

from types import ModuleType, SimpleNamespace

__all__ = ["build_fastapi_stub"]


def build_fastapi_stub() -> dict[str, ModuleType]:
    module = ModuleType("fastapi")
    module.status = SimpleNamespace()
    return {"fastapi": module}
