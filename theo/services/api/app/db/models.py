"""Backward-compatible shims for relocated persistence models."""
from __future__ import annotations

from warnings import warn

warn(
    "theo.services.api.app.db.models is deprecated; import from "
    "theo.adapters.persistence.models instead",
    DeprecationWarning,
    stacklevel=2,
)

from theo.services.api.app.persistence_models import *  # noqa: F401,F403
from theo.services.api.app.persistence_models import __all__ as __all__  # type: ignore
