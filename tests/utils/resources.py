"""Shared resource helpers for integration-heavy tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

try:  # pragma: no cover - optional dependency in thin environments
    from sqlalchemy.engine import Engine
except ModuleNotFoundError:  # pragma: no cover - fallback when SQLAlchemy absent
    class Engine:  # type: ignore[no-redef]
        pass

__all__ = ["TestResourcePool"]


@dataclass
class TestResourcePool:
    """Pool expensive resources for reuse across the test session."""

    _engines: Dict[str, Engine] = field(default_factory=dict)

    def get_db_engine(self, url: str) -> Engine:
        engine = self._engines.get(url)
        if engine is None:
            from sqlalchemy import create_engine

            engine = create_engine(url, future=True)
            self._engines[url] = engine
        return engine

    def cleanup(self) -> None:
        for engine in self._engines.values():
            engine.dispose()
        self._engines.clear()
