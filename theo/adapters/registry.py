"""Simple adapter registry enabling dependency-injected wiring."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict


_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AdapterRegistry:
    """Stores factories for driven adapters keyed by port name.
    
    Supports controlled override scenarios for testing and reconfiguration.
    """

    factories: Dict[str, Callable[[], Any]] = field(default_factory=dict)

    def register(self, port: str, factory: Callable[[], Any], *, allow_override: bool = False) -> None:
        """Register a factory for the given port.
        
        Args:
            port: The port name to register
            factory: Factory function that creates the adapter instance
            allow_override: If True, allows replacing existing registrations
            
        Raises:
            ValueError: When port is already registered and allow_override=False
        """
        if port in self.factories and not allow_override:
            existing_factory = self.factories[port]
            raise ValueError(
                f"Adapter already registered for port '{port}' "
                f"(existing: {existing_factory.__name__ if hasattr(existing_factory, '__name__') else existing_factory}). "
                f"Use allow_override=True to replace or call unregister() first."
            )
            
        if port in self.factories and allow_override:
            _LOGGER.debug(
                "Overriding existing adapter registration for port '%s'", 
                port
            )
            
        self.factories[port] = factory

    def unregister(self, port: str) -> bool:
        """Remove registration for a port.
        
        Args:
            port: The port name to unregister
            
        Returns:
            True if port was registered and removed, False if not found
        """
        removed = self.factories.pop(port, None) is not None
        if removed:
            _LOGGER.debug("Unregistered adapter for port '%s'", port)
        return removed

    def clear(self) -> None:
        """Remove all registered adapters.
        
        Useful for test teardown and registry reset scenarios.
        """
        port_count = len(self.factories)
        self.factories.clear()
        _LOGGER.debug("Cleared %d adapter registrations", port_count)

    def is_registered(self, port: str) -> bool:
        """Check if a port has a registered adapter.
        
        Args:
            port: The port name to check
            
        Returns:
            True if port is registered, False otherwise
        """
        return port in self.factories

    def get_registered_ports(self) -> list[str]:
        """Get list of all registered port names.
        
        Returns:
            Sorted list of registered port names
        """
        return sorted(self.factories.keys())

    def resolve(self, port: str) -> Any:
        """Resolve a concrete adapter instance.
        
        Args:
            port: The port name to resolve
            
        Returns:
            The adapter instance created by the registered factory
            
        Raises:
            LookupError: When no adapter is registered for the port
        """
        try:
            factory = self.factories[port]
        except KeyError as exc:  # pragma: no cover - defensive guard
            available_ports = ", ".join(self.get_registered_ports()) if self.factories else "(none)"
            raise LookupError(
                f"Adapter for port '{port}' is not registered. "
                f"Available ports: {available_ports}"
            ) from exc
            
        try:
            return factory()
        except Exception as exc:
            _LOGGER.error(
                "Failed to create adapter instance for port '%s': %s", 
                port, exc, exc_info=True
            )
            raise
