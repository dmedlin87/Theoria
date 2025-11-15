"""Shared SQLAlchemy primitives exposed to the application layer when needed."""

from __future__ import annotations

from sqlalchemy import delete, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

__all__ = [
    "delete",
    "pg_insert",
    "select",
    "sqlite_insert",
    "SQLAlchemyError",
    "Session",
    "tuple_",
]
