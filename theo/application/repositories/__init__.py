"""Repository interfaces for application layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from .chat_repository import ChatSessionRepository
    from .discovery_repository import DiscoveryRepository
    from .document_repository import DocumentRepository
    from .ingestion_job_repository import IngestionJobRepository

__all__ = [
    "ChatSessionRepository",
    "DiscoveryRepository",
    "DocumentRepository",
    "IngestionJobRepository",
]


def __getattr__(name: str):  # pragma: no cover - exercised implicitly in tests
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib import import_module

    module_name = {
        "ChatSessionRepository": ".chat_repository",
        "DiscoveryRepository": ".discovery_repository",
        "DocumentRepository": ".document_repository",
        "IngestionJobRepository": ".ingestion_job_repository",
    }[name]

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
