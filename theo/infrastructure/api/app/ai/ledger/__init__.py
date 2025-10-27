"""Usage tracking utilities for AI modules.

The new ``ai/ledger/`` package co-exists with the legacy ``ai/ledger.py``
module while Phase 2 migrations proceed.  Import the historical ``CacheRecord``
and ``SharedLedger`` symbols from the legacy module using an explicit loader so
``from theo.infrastructure.api.app.ai.ledger import CacheRecord`` continues to work
without triggering circular imports.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from .usage_tracker import UsageTracker

_LEGACY_PATH = Path(__file__).resolve().parent.parent / "ledger.py"
_LEGACY_SPEC = importlib.util.spec_from_file_location(
    "theo.infrastructure.api.app.ai._legacy_ledger",
    _LEGACY_PATH,
)
if _LEGACY_SPEC is None or _LEGACY_SPEC.loader is None:  # pragma: no cover - safety guard
    raise ImportError("Unable to load legacy ledger module")

_LEGACY_MODULE = importlib.util.module_from_spec(_LEGACY_SPEC)
sys.modules.setdefault(_LEGACY_SPEC.name, _LEGACY_MODULE)
_LEGACY_SPEC.loader.exec_module(_LEGACY_MODULE)

CacheRecord = _LEGACY_MODULE.CacheRecord
SharedLedger = _LEGACY_MODULE.SharedLedger

__all__ = ["CacheRecord", "SharedLedger", "UsageTracker"]
