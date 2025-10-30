"""Shared fixtures for evidence tests."""

from __future__ import annotations

import sys
import types

import pytest


@pytest.fixture(scope="session", autouse=True)
def stub_fastapi_module() -> None:
    """Provide a lightweight ``fastapi.status`` stub for import-time checks."""

    if "fastapi" in sys.modules:
        return

    fastapi_module = types.ModuleType("fastapi")
    status_module = types.SimpleNamespace(HTTP_422_UNPROCESSABLE_ENTITY=422)
    fastapi_module.status = status_module  # type: ignore[attr-defined]
    sys.modules["fastapi"] = fastapi_module
