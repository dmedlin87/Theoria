"""Bootstrap helpers wiring adapters to application services."""
from __future__ import annotations

from typing import Any, Callable

from theo.adapters import AdapterRegistry
from theo.application import ApplicationContainer


def bootstrap_application(
    *,
    registry: AdapterRegistry,
    command_factory: Callable[[], Any],
    retire_factory: Callable[[], Any],
    get_factory: Callable[[], Any],
    list_factory: Callable[[], Any],
    research_factory: Callable[[], Any],
) -> ApplicationContainer:
    """Construct an :class:`ApplicationContainer` wired to registered adapters."""

    ingest = command_factory()
    retire = retire_factory()
    get = get_factory()
    list_docs = list_factory()
    research = research_factory

    return ApplicationContainer(
        ingest_document=ingest,
        retire_document=retire,
        get_document=get,
        list_documents=list_docs,
        research_service_factory=research,
    )
