"""Simple adapter registry enabling dependency-injected wiring."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict


@dataclass(slots=True)
class AdapterRegistry:
    """Stores factories for driven adapters keyed by port name."""

    factories: Dict[str, Callable[[], Any]] = field(default_factory=dict)

    def register(self, port: str, factory: Callable[[], Any]) -> None:
        """Register a factory for the given port."""

        if port in self.factories:
            raise ValueError(f"Adapter already registered for port '{port}'")
        self.factories[port] = factory

    def resolve(self, port: str) -> Any:
        """Resolve a concrete adapter instance."""

        try:
            factory = self.factories[port]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise LookupError(f"Adapter for port '{port}' is not registered") from exc
        return factory()
