"""Runtime feature flags for Theo Engine startup behaviours."""

from __future__ import annotations

import os
from functools import lru_cache


_TRUTHY_VALUES = {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def allow_insecure_startup() -> bool:
    """Return True when insecure startup overrides are permitted."""

    value = os.getenv("THEO_ALLOW_INSECURE_STARTUP", "")
    return value.lower() in _TRUTHY_VALUES


__all__ = ["allow_insecure_startup"]

