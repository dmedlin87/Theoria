"""Framework-specific adapters for application interfaces."""

from .resilience import CircuitBreakerResiliencePolicy, resilience_policy_factory
from .security import FastAPIPrincipalResolver, configure_principal_resolver, require_principal
from .telemetry import ApiTelemetryProvider

__all__ = [
    "ApiTelemetryProvider",
    "CircuitBreakerResiliencePolicy",
    "FastAPIPrincipalResolver",
    "configure_principal_resolver",
    "require_principal",
    "resilience_policy_factory",
]
