"""CLI entry point for running the Theo Engine MCP server."""

from __future__ import annotations

import os
from typing import Final

import uvicorn


def _env_flag(name: str, default: str = "0") -> bool:
    raw = os.getenv(name, default)
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    """Run the MCP server via `python -m mcp_server`."""

    host: Final[str] = os.getenv("MCP_HOST", "127.0.0.1")
    port_raw = os.getenv("MCP_PORT") or os.getenv("PORT") or "8050"
    try:
        port = int(port_raw)
    except ValueError:  # pragma: no cover - defensive guard
        raise SystemExit(f"Invalid MCP_PORT value: {port_raw!r}") from None

    reload_enabled = _env_flag("MCP_RELOAD", "0")

    uvicorn.run(
        "mcp_server.server:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level=os.getenv("MCP_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
