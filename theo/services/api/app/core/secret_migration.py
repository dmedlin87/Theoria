"""Legacy shim forwarding to :mod:`theo.application.facades.secret_migration`."""
from __future__ import annotations

from warnings import warn

from theo.application.facades.secret_migration import migrate_secret_settings

warn(
    "Importing from 'theo.services.api.app.core.secret_migration' is deprecated; "
    "use 'theo.application.facades.secret_migration' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["migrate_secret_settings"]
