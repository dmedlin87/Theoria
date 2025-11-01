"""Registry helpers for wiring Theo's MCP tool handlers into the server."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, MutableMapping

from sqlalchemy.orm import Session

try:  # pragma: no cover - guarded for environments missing infrastructure deps
    from theo.infrastructure.api.app.mcp.tools import (
        MCPToolError as _InfrastructureMCPToolError,
    )
    from theo.infrastructure.api.app.mcp.tools import (
        handle_note_write as _infrastructure_handle_note_write,
    )
except Exception as exc:  # pragma: no cover - fallback path for lightweight test envs
    class _FallbackMCPToolError(ValueError):
        """Raised when infrastructure dependencies are unavailable."""

        __cause__ = exc

    def _infrastructure_handle_note_write(*_args: Any, **_kwargs: Any):
        raise _FallbackMCPToolError(
            "Infrastructure MCP tooling is unavailable in this environment"
        )

    _InfrastructureMCPToolError = _FallbackMCPToolError

# Re-export the infrastructure handler and error for callers that previously
# imported them from the infrastructure package.
handle_note_write = _infrastructure_handle_note_write
MCPToolError = _InfrastructureMCPToolError

ToolHandler = Callable[[Session, Mapping[str, Any]], Any]


@dataclass(frozen=True)
class ToolRegistration:
    """Metadata describing a single MCP tool entrypoint."""

    name: str
    handler: ToolHandler
    requires_commit: bool


class _ToolRegistry:
    """Mutable registry of MCP tool handlers keyed by name."""

    def __init__(self) -> None:
        self._registrations: MutableMapping[str, ToolRegistration] = {}

    def register(
        self,
        name: str,
        handler: ToolHandler,
        *,
        requires_commit: bool = True,
    ) -> None:
        """Register a new MCP tool handler under the provided name."""

        if not isinstance(name, str):
            raise TypeError("MCP tool name must be a string")
        normalized = name.strip()
        if not normalized:
            raise ValueError("MCP tool name must be a non-empty string")
        if not callable(handler):
            raise TypeError("MCP tool handler must be callable")
        if normalized in self._registrations:
            raise ValueError(f"MCP tool '{normalized}' is already registered")

        registration = ToolRegistration(
            name=normalized,
            handler=handler,
            requires_commit=bool(requires_commit),
        )
        self._registrations[normalized] = registration

    def get(self, name: str) -> ToolRegistration:
        """Return the registration for ``name`` if one exists."""

        normalized = name.strip() if isinstance(name, str) else ""
        if not normalized or normalized not in self._registrations:
            raise KeyError(f"MCP tool '{name}' is not registered")
        return self._registrations[normalized]

    def items(self) -> Iterable[ToolRegistration]:
        """Return the registered tools."""

        return tuple(self._registrations.values())

    def invoke(self, name: str, session: Session, payload: Mapping[str, Any]) -> Any:
        """Invoke the tool handler associated with ``name``."""

        registration = self.get(name)
        return registration.handler(session, payload)


def _build_default_registry() -> _ToolRegistry:
    """Populate a registry with Theo's default MCP tools."""

    registry = _ToolRegistry()
    registry.register("note_write", handle_note_write, requires_commit=True)
    return registry


_registry = _build_default_registry()


def register_tool(
    name: str,
    handler: ToolHandler,
    *,
    requires_commit: bool = True,
) -> None:
    """Register an additional MCP tool handler."""

    _registry.register(name, handler, requires_commit=requires_commit)


def iter_registered_tools() -> Iterable[ToolRegistration]:
    """Yield all registered tool definitions."""

    return _registry.items()


def invoke_tool(name: str, session: Session, payload: Mapping[str, Any]) -> Any:
    """Invoke a registered tool handler with the supplied context."""

    return _registry.invoke(name, session, payload)


def register_with_server(server: Any) -> None:
    """Register all known MCP tools with ``server``.

    ``server`` is expected to expose a ``register_tool`` method that accepts the
    tool name along with keyword arguments for ``handler`` and ``requires_commit``.
    The fake MCP server used in tests implements the same surface as the real
    server, allowing us to verify registration ordering and metadata without
    depending on the FastAPI app.
    """

    for registration in iter_registered_tools():
        server.register_tool(
            registration.name,
            handler=registration.handler,
            requires_commit=registration.requires_commit,
        )


__all__ = [
    "MCPToolError",
    "ToolRegistration",
    "handle_note_write",
    "iter_registered_tools",
    "invoke_tool",
    "register_tool",
    "register_with_server",
]
