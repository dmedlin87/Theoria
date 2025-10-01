"""Utilities for reporting application version details."""

from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def get_git_sha() -> str | None:
    """Return the current Git SHA if available."""

    git_executable = shutil.which("git")
    if not git_executable:
        return None

    try:
        result = subprocess.run(  # noqa: S603 - bounded git invocation for version metadata
            [git_executable, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip() or None


__all__ = ["get_git_sha"]
