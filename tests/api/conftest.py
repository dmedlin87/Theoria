"""Shared test configuration for API-level tests."""

from __future__ import annotations

import os

os.environ.setdefault("SETTINGS_SECRET_KEY", "test-secret-key")
