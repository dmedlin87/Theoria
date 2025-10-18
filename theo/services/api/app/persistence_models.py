"""Service-layer access to persistence models without direct ORM imports."""
from __future__ import annotations

import importlib
from typing import Any

_MODELS = importlib.import_module("theo.adapters.persistence.models")

__all__ = [name for name in dir(_MODELS) if not name.startswith("_")]

def __getattr__(name: str) -> Any:
    if name in __all__:
        return getattr(_MODELS, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
