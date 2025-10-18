"""Configuration constants for the local :mod:`faker` test stub.

This mirrors the upstream package's interface just enough for the pytest
plugin shim to import ``DEFAULT_LOCALE`` without pulling in the real
third-party dependency.
"""

DEFAULT_LOCALE = "en_US"
