"""CLI test configuration and shared fixtures."""

from __future__ import annotations

import sys

from tests.stubs.fastapi import build_fastapi_stub
from tests.stubs.sqlalchemy import build_sqlalchemy_stubs

for name, module in {**build_fastapi_stub(), **build_sqlalchemy_stubs()}.items():
    sys.modules.setdefault(name, module)
