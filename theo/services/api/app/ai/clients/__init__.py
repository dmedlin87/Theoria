"""Client implementations for the modular AI stack."""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

from .anthropic_client import AnthropicClient
from .factory import AIClientFactory
from .openai_client import OpenAIClient


def _load_legacy_clients() -> ModuleType:
    """Load the legacy ``clients.py`` module for backward compatibility."""

    module_name = f"{__name__}.__legacy"
    legacy_path = Path(__file__).resolve().parent.parent / "clients.py"
    spec = spec_from_file_location(module_name, legacy_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Cannot load legacy clients module from {legacy_path}")
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr[arg-type]]
    return module


_legacy_clients: ModuleType | None = None


def __getattr__(name: str) -> Any:
    """Expose legacy helpers (``build_client`` & friends) on demand."""

    global _legacy_clients
    if _legacy_clients is None:
        _legacy_clients = _load_legacy_clients()
        legacy_all = getattr(_legacy_clients, "__all__", ())
        for export in legacy_all:
            if export not in __all__:
                __all__.append(export)
    try:
        return getattr(_legacy_clients, name)
    except AttributeError as exc:  # pragma: no cover - mirrors module behaviour
        raise AttributeError(name) from exc


__all__ = ["AIClientFactory", "AnthropicClient", "OpenAIClient", "build_client"]
