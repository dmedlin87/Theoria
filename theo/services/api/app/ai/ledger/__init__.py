"""Shared ledger utilities for AI workflows."""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

from .usage_tracker import UsageTracker

__all__ = ["UsageTracker", "CacheRecord", "SharedLedger"]


_legacy_ledger: ModuleType | None = None


def _load_legacy_ledger() -> ModuleType:
    """Load the legacy ``ledger.py`` module when compatibility helpers are requested."""

    module_name = f"{__name__}.__legacy"
    legacy_path = Path(__file__).resolve().parent.parent / "ledger.py"
    spec = spec_from_file_location(module_name, legacy_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Cannot load legacy ledger module from {legacy_path}")
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr[arg-type]]
    return module


def __getattr__(name: str) -> Any:
    """Provide access to legacy ledger constructs such as ``CacheRecord``."""

    global _legacy_ledger
    if _legacy_ledger is None:
        _legacy_ledger = _load_legacy_ledger()
        legacy_all = getattr(_legacy_ledger, "__all__", ())
        for export in legacy_all:
            if export not in __all__:
                __all__.append(export)
    try:
        return getattr(_legacy_ledger, name)
    except AttributeError as exc:  # pragma: no cover - maintain module semantics
        raise AttributeError(name) from exc
