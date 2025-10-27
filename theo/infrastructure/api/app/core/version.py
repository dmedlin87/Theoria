"""Legacy shim for :mod:`theo.application.facades.version`.

``get_git_sha`` used to be imported from this module.  The facade now
provides the canonical implementation; we simply re-export it while
issuing a deprecation warning for the legacy path.
"""

from __future__ import annotations

import warnings

from theo.application.facades import version as _facade

warnings.warn(
    "Importing 'theo.infrastructure.api.app.core.version' is deprecated. "
    "Use 'theo.application.facades.version' instead.",
    DeprecationWarning,
    stacklevel=2,
)

get_git_sha = _facade.get_git_sha

__all__ = ["get_git_sha"]
