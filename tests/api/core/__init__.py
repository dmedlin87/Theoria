"""Test helpers for legacy core shim modules."""
from __future__ import annotations

import importlib
import sys
import warnings
from types import ModuleType
from warnings import WarningMessage


def import_legacy_module(module_name: str) -> tuple[ModuleType, WarningMessage]:
    """Import a legacy core module and capture its deprecation warning."""
    sys.modules.pop(module_name, None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        module = importlib.import_module(module_name)

    for warning in caught:
        if issubclass(warning.category, DeprecationWarning):
            return module, warning
    raise AssertionError(f"No DeprecationWarning emitted when importing {module_name}")
