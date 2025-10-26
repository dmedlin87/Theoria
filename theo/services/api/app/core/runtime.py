"""Legacy runtime shim that forwards to :mod:`theo.application.facades.runtime`.

Historically :func:`allow_insecure_startup` lived in this module.  The
public facade now owns the implementation but we keep a thin wrapper that
re-exports the original helper and warns during import.  The function
object itself is not wrapped so call-site semantics (memoisation and
warning behaviour within the facade) remain untouched.
"""

from __future__ import annotations

import warnings

from theo.application.facades import runtime as _facade

warnings.warn(
    "Importing 'theo.services.api.app.core.runtime' is deprecated. "
    "Use 'theo.application.facades.runtime' instead.",
    DeprecationWarning,
    stacklevel=2,
)

allow_insecure_startup = _facade.allow_insecure_startup

__all__ = ["allow_insecure_startup"]
