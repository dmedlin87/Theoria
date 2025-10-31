"""Citation helpers for evidence workflows."""

from __future__ import annotations

import re
from functools import lru_cache

_CSL_CITEKEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_:+\-.]{2,63}$")


@lru_cache(maxsize=1024)
def is_valid_csl_citekey(value: str | None) -> bool:
    """Return ``True`` when ``value`` matches the CSL citekey format."""

    if not value:
        return False
    if len(value) > 64:
        return False
    return bool(_CSL_CITEKEY_PATTERN.fullmatch(value))


__all__ = ["is_valid_csl_citekey"]
