"""Integration tests for the service-level MCP tool registry."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from theo.services.api.app.mcp import tools


class _FakeServer:
    """Minimal MCP server stub used to capture registration calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object, bool]] = []

    def register_tool(self, name: str, *, handler, requires_commit: bool) -> None:
        self.calls.append((name, handler, requires_commit))


@pytest.fixture
def fresh_registry(monkeypatch):
    """Reset the MCP registry to its default state for each test."""

    registry = tools._build_default_registry()
    monkeypatch.setattr(tools, "_registry", registry)
    return registry


@pytest.fixture
def fake_session():
    return SimpleNamespace()


def _sample_payload(**overrides):
    payload = {
        "osis": "John.3.16",
        "body": "For God so loved the world",
        "title": "Gospel Insight",
    }
    payload.update(overrides)
    return payload


def test_register_with_server_registers_default_tool(fresh_registry):
    server = _FakeServer()

    tools.register_with_server(server)

    assert len(server.calls) == 1
    name, handler, requires_commit = server.calls[0]
    assert name == "note_write"
    assert handler is tools.handle_note_write
    assert requires_commit is True


def test_invoke_tool_delegates_to_handler(monkeypatch, fake_session, mcp_security_policies):
    captured: dict[str, object] = {}

    def fake_handle(session, payload):
        captured["session"] = session
        captured["payload"] = payload
        return {"note_id": "note-1"}

    monkeypatch.setattr(tools, "handle_note_write", fake_handle)
    registry = tools._build_default_registry()
    monkeypatch.setattr(tools, "_registry", registry)

    payload = _sample_payload(commit=True)
    result = tools.invoke_tool("note_write", fake_session, payload)

    assert result == {"note_id": "note-1"}
    assert captured["session"] is fake_session
    assert captured["payload"] is payload


def test_invoke_tool_propagates_mcp_error(monkeypatch, fake_session, mcp_security_policies):
    def fake_handle(session, payload):
        raise tools.MCPToolError("invalid payload")

    monkeypatch.setattr(tools, "handle_note_write", fake_handle)
    registry = tools._build_default_registry()
    monkeypatch.setattr(tools, "_registry", registry)

    with pytest.raises(tools.MCPToolError) as excinfo:
        tools.invoke_tool("note_write", fake_session, _sample_payload(osis=""))
    assert "invalid payload" in str(excinfo.value)


def test_register_tool_prevents_duplicate_registration(fresh_registry):
    with pytest.raises(ValueError):
        tools.register_tool("note_write", lambda *args, **kwargs: None)


def test_register_tool_rejects_blank_name(fresh_registry):
    with pytest.raises(ValueError):
        tools.register_tool("   ", lambda *args, **kwargs: None)


def test_invoke_tool_unknown_tool_raises_key_error(fresh_registry, fake_session):
    with pytest.raises(KeyError):
        tools.invoke_tool("nonexistent", fake_session, _sample_payload())


def test_register_tool_respects_requires_commit_flag(fresh_registry):
    preview_result = {"status": "preview"}

    def fake_preview(session, payload):
        return preview_result

    tools.register_tool("preview_only", fake_preview, requires_commit=False)
    server = _FakeServer()
    tools.register_with_server(server)

    preview_entry = next((call for call in server.calls if call[0] == "preview_only"), None)
    assert preview_entry is not None
    name, handler, requires_commit = preview_entry
    assert name == "preview_only"
    assert handler is fake_preview
    assert requires_commit is False


def test_register_tool_normalizes_name(fresh_registry, fake_session):
    def fake_preview(session, payload):
        return {"status": "ok"}

    tools.register_tool("  preview_only  ", fake_preview, requires_commit=False)

    result = tools.invoke_tool("preview_only", fake_session, _sample_payload(commit=False))
    assert result == {"status": "ok"}
