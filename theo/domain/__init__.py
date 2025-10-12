"""Domain core aggregates, value objects, and business policies.

This package is intentionally framework-agnostic. Only standard library,
`dataclasses`, and `pydantic` types are permitted.
"""

from .documents import Document, DocumentId, DocumentMetadata
from .references import ScriptureReference

__all__ = [
    "Document",
    "DocumentId",
    "DocumentMetadata",
    "ScriptureReference",
]
