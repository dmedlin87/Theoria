"""Compatibility shims for legacy core imports.

These modules mirror :mod:`theo.application.facades` symbols so that
imports such as ``theo.infrastructure.api.app.core.database`` continue to work
while emitting deprecation warnings.  Only the facade objects are
re-exported; no additional behaviour should be added here.
"""

from __future__ import annotations

__all__ = []
