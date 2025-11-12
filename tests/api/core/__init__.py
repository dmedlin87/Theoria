"""Test helpers for application facade modules."""
from __future__ import annotations

import importlib
import sys
from types import ModuleType


def reload_facade(module_name: str) -> ModuleType:
    """Reload a facade module ensuring tests observe fresh state."""

    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)
