"""Persistence adapters providing database bindings and utilities."""
from __future__ import annotations

from .models import Base
from .sqlite import dispose_sqlite_engine

__all__ = ["Base", "dispose_sqlite_engine"]
