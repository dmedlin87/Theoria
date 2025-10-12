"""Application service layer orchestrating domain operations.

The application layer exposes facades that coordinate repositories, search
clients, and AI adapters. Interfaces are defined via structural typing so that
adapters can be swapped without modifying business workflows.
"""

from .interfaces import CommandService, QueryService
from .services import ApplicationContainer

__all__ = ["CommandService", "QueryService", "ApplicationContainer"]
