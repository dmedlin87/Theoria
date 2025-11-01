"""Model Context Protocol adapters for Theo's API surface."""

from .tools import MCPToolError, register_tool, invoke_tool, register_with_server

__all__ = ["MCPToolError", "register_tool", "invoke_tool", "register_with_server"]
