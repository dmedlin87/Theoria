"""Evidence-focused regression tests."""

from __future__ import annotations

import sys
import types

if "fastapi" not in sys.modules:
    fastapi_module = types.ModuleType("fastapi")
    status_module = types.SimpleNamespace(HTTP_422_UNPROCESSABLE_CONTENT=422)
    fastapi_module.status = status_module  # type: ignore[attr-defined]
    sys.modules["fastapi"] = fastapi_module
