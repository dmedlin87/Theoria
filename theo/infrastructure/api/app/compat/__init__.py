"""Backward-compatible shims for legacy import paths.

Historically the services API exposed helpers under
``theo.infrastructure.api.app.core``.  Those implementations were moved into
:mod:`theo.application.facades`, but downstream callers still rely on the
old paths.  The modules in :mod:`theo.infrastructure.api.app.core` therefore
*only* re-export facade symbols and emit a :class:`DeprecationWarning`
when imported.  Whenever a facade gains a new helper that used to live in
the legacy namespace, add it to the matching shim module so importing
code continues to function while surfacing a migration hint.
"""
