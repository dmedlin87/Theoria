"""Test configuration for MCP tools."""

import os

os.environ.setdefault("MCP_TOOLS_ENABLED", "1")
os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("THEORIA_ENVIRONMENT", "development")
