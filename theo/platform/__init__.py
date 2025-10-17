"""Shared platform services (telemetry, security policies, bootstrap)."""

from .bootstrap import bootstrap_application
from .events import EventBus, event_bus

__all__ = ["bootstrap_application", "EventBus", "event_bus"]
