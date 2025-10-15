"""Utilities for lazily importing optional modules."""

from __future__ import annotations

from importlib import import_module
from threading import Lock
from types import ModuleType
from typing import Any


class LazyImportModule:
    """Proxy that loads a module on first attribute access."""

    def __init__(self, dotted_path: str) -> None:
        self._dotted_path = dotted_path
        self._module: ModuleType | None = None
        self._lock = Lock()

    def load(self) -> ModuleType:
        """Import and cache the target module."""

        module = self._module
        if module is None:
            with self._lock:
                module = self._module
                if module is None:
                    module = import_module(self._dotted_path)
                    self._module = module
        return module

    def __getattr__(self, item: str) -> Any:  # pragma: no cover - thin proxy
        return getattr(self.load(), item)

    def __dir__(self) -> list[str]:  # pragma: no cover - debug helper
        module = self._module
        if module is None:
            module = self.load()
        return sorted(set(dir(module)))


__all__ = ["LazyImportModule"]
