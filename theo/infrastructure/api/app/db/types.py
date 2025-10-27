"""Backward-compatible shim for relocated database type decorators."""
from __future__ import annotations

from warnings import warn

warn(
    "theo.infrastructure.api.app.db.types is deprecated; import from "
    "theo.adapters.persistence.types instead",
    DeprecationWarning,
    stacklevel=2,
)

from theo.adapters.persistence.types import *  # noqa: F401,F403
from theo.adapters.persistence.types import __all__ as __all__  # type: ignore
