from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session


def get_session() -> Iterator[Session]: ...
