"""Test configuration for MCP tools."""

from __future__ import annotations

import os
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

try:  # pragma: no cover - import guarded for optional dependency chain
    from mcp_server.security import (
        reset_read_security_policy,
        reset_write_security_policy,
    )
except Exception:  # pragma: no cover - fallback when FastAPI/Starlette missing
    reset_read_security_policy = None  # type: ignore[assignment]
    reset_write_security_policy = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency guard
    from mcp_server.tools import read, write
except Exception:  # pragma: no cover - fallback when FastAPI/Starlette missing
    read = None  # type: ignore[assignment]
    write = None  # type: ignore[assignment]

os.environ.setdefault("MCP_TOOLS_ENABLED", "1")
os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("THEORIA_ENVIRONMENT", "development")


@contextmanager
def _fake_session_scope():
    """Provide an in-memory SQLAlchemy session substitute for tool tests."""

    yield SimpleNamespace()


@pytest.fixture
def mcp_session_scope(monkeypatch):
    """Patch MCP read/write tools to use the in-memory session scope."""

    if read is None or write is None:  # pragma: no cover - dependency missing
        yield _fake_session_scope
        return

    monkeypatch.setattr(read, "_session_scope", _fake_session_scope)
    monkeypatch.setattr(write, "_session_scope", _fake_session_scope)
    yield _fake_session_scope


@pytest.fixture
def mcp_security_policies(monkeypatch):
    """Reset MCP security policies to a neutral state for each test."""

    if reset_write_security_policy is None or reset_read_security_policy is None:  # pragma: no cover
        yield
        return

    reset_write_security_policy()
    reset_read_security_policy()
    monkeypatch.delenv("MCP_WRITE_ALLOWLIST", raising=False)
    monkeypatch.delenv("MCP_WRITE_RATE_LIMITS", raising=False)
    monkeypatch.delenv("MCP_READ_RATE_LIMITS", raising=False)
    yield
    reset_write_security_policy()
    reset_read_security_policy()
