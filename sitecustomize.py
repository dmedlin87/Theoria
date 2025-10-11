from __future__ import annotations

import warnings

# Suppress noisy deprecation warnings emitted by schemathesis' dependency on
# jsonschema internals. These warnings are acknowledged upstream and do not
# impact functionality or test coverage.
warnings.filterwarnings(
    "ignore",
    message="jsonschema.exceptions.RefResolutionError is deprecated",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message="jsonschema.RefResolver is deprecated as of v4.18.0",
    category=DeprecationWarning,
)

# Silence SQLAlchemy metadata teardown warnings that are triggered during
# drop_all in tests using in-memory SQLite. These warnings are benign for the
# test suite and would otherwise obscure actionable output.
try:
    from sqlalchemy.exc import SAWarning
except Exception:  # pragma: no cover - SQLAlchemy is always available in tests
    SAWarning = None
else:
    warnings.filterwarnings(
        "ignore",
        message="Can't sort tables for DROP; an unresolvable foreign key dependency exists between tables",
        category=SAWarning,
    )
