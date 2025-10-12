"""Domain document aggregate definitions.

These objects capture the minimum stable fields shared across adapters. They
should not include persistence-specific metadata (timestamps, revision IDs, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import NewType

DocumentId = NewType("DocumentId", str)


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    """Metadata fields describing a theological document."""

    title: str
    source: str
    language: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Document:
    """Domain aggregate representing an indexed document."""

    id: DocumentId
    metadata: DocumentMetadata
    scripture_refs: tuple[str, ...]
    tags: tuple[str, ...] = ()
    checksum: str | None = None
