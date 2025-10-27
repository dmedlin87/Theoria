"""Reusable stub modules for the test-suite."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import ModuleType
from typing import Mapping

__all__ = [
    "install_modules",
]


@contextmanager
def install_modules(modules: Mapping[str, ModuleType], *, registry: dict[str, ModuleType] | None = None) -> Iterator[None]:
    """Temporarily register a mapping of module names in ``sys.modules``.

    The helper is intentionally minimal so it can be reused in tests without
    pulling in ``pytest`` or ``monkeypatch`` fixtures.
    """

    import sys

    registry = registry or sys.modules
    missing = {name: module for name, module in modules.items() if name not in registry}
    registry.update(missing)
    try:
        yield
    finally:
        for name in missing:
            registry.pop(name, None)
