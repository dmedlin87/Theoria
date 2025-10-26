"""Application service layer orchestrating domain operations.

The application layer exposes facades that coordinate repositories, search
clients, and AI adapters. Interfaces are defined via structural typing so that
adapters can be swapped without modifying business workflows.

Historically this module eagerly imported several submodules. While convenient,
it meant importing :mod:`theo.application` attempted to load optional
dependencies (for example the ``pythonbible`` package used by research
features). Test fixtures and adapters that only require configuration helpers
should not need to install those extras. To keep the public API intact while
making imports safe in lightweight environments, the re-exports are resolved
on-demand using ``__getattr__``.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "CommandService",
    "QueryService",
    "ApplicationContainer",
    "ReportSection",
    "ResearchReport",
    "ResearchService",
]

_ATTRIBUTE_EXPORTS = {
    "CommandService": ("theo.application.interfaces", "CommandService"),
    "QueryService": ("theo.application.interfaces", "QueryService"),
    "ApplicationContainer": (
        "theo.application.services",
        "ApplicationContainer",
    ),
    "ReportSection": ("theo.application.research", "ReportSection"),
    "ResearchReport": ("theo.application.research", "ResearchReport"),
    "ResearchService": ("theo.application.research", "ResearchService"),
}


def __getattr__(name: str) -> Any:
    """Lazily import public application layer exports.

    This avoids importing heavyweight optional dependencies during module
    initialization while keeping backwards compatibility for callers relying on
    ``from theo.application import <symbol>``.
    """

    if name in _ATTRIBUTE_EXPORTS:
        module_name, attribute = _ATTRIBUTE_EXPORTS[name]
        module = import_module(module_name)
        value = getattr(module, attribute)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
