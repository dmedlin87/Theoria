"""Compatibility shim for :mod:`theo.application.facades.secret_migration`.

The historic module exposed :func:`migrate_secret_settings`.  This shim
re-exports the facade helper verbatim so that older ingestion scripts can
still import it while receiving a deprecation warning.
"""

from __future__ import annotations

import warnings

from theo.application.facades import secret_migration as _facade

warnings.warn(
    "Importing 'theo.infrastructure.api.app.core.secret_migration' is deprecated. "
    "Use 'theo.application.facades.secret_migration' instead.",
    DeprecationWarning,
    stacklevel=2,
)

migrate_secret_settings = _facade.migrate_secret_settings

__all__ = ["migrate_secret_settings"]
