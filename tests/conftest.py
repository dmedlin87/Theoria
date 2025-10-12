from __future__ import annotations

import os
import sys
from pathlib import Path

pytest_plugins = (
    "theo.tests.coverage_stub",
    "theo.tests.pgvector_harness",
)

os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
