"""Ingestion helpers exposed for external callers."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "HTRClientProtocol",
    "HTRResult",
    "generate_tei_markup",
    "ingest_pilot_corpus",
]

if TYPE_CHECKING:  # pragma: no cover - import side effects only needed for typing
    from .tei_pipeline import (  # noqa: F401 - re-exported via ``__getattr__``
        HTRClientProtocol,
        HTRResult,
        generate_tei_markup,
        ingest_pilot_corpus,
    )


def __getattr__(name: str) -> Any:
    """Provide lazy access to heavy ingestion helpers."""

    if name in __all__:
        module = import_module(".tei_pipeline", __name__)
        return getattr(module, name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    """Expose re-exported symbols when using ``dir()`` for introspection."""

    return sorted(__all__ + list(globals().keys()))
