"""Minimal pytest plugin shim for environments without Celery installed."""

from __future__ import annotations

import pytest


@pytest.fixture
def celery_app():  # pragma: no cover - exercised indirectly in tests
    """Default celery_app fixture placeholder.

    The real Celery plugin supplies a richer fixture, but for the worker tests we
    only need a stub that can be overridden within the suite.  Returning ``None``
    keeps pytest satisfied while allowing test modules to provide their own
    implementation with the same name.
    """

    return None


__all__ = ["celery_app"]
