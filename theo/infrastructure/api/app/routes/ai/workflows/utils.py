"""Utility helpers shared across workflow routes."""

from __future__ import annotations

from theo.application.facades import telemetry  # noqa: F401

from theo.infrastructure.api.app.models.search import HybridSearchFilters


def has_filters(filters: HybridSearchFilters | None) -> bool:
    """Return ``True`` when *filters* contains at least one non-null field."""

    if not filters:
        return False
    return bool(filters.model_dump(exclude_none=True))


__all__ = ["has_filters"]
