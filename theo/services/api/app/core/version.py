"""Legacy shim forwarding to :mod:`theo.application.facades.version`."""
from __future__ import annotations

from warnings import warn

from theo.application.facades.version import get_git_sha

warn(
    "Importing from 'theo.services.api.app.core.version' is deprecated; "
    "use 'theo.application.facades.version' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["get_git_sha"]
