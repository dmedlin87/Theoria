"""Utilities for reporting application version details."""

from __future__ import annotations

import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def get_git_sha() -> str | None:
    """Return the current Git SHA if available."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip() or None


__all__ = ["get_git_sha"]
