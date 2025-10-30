"""High level automation for curating evidence corpora."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .indexer import EvidenceIndexer
from .models import EvidenceCollection
from .utils import dump_records
from .validator import EvidenceValidator


class EvidencePromoter:
    """Coordinate validation, normalization, and indexing flows."""

    def __init__(
        self,
        *,
        validator: EvidenceValidator | None = None,
        indexer: EvidenceIndexer | None = None,
    ) -> None:
        self.validator = validator or EvidenceValidator()
        self.indexer = indexer or EvidenceIndexer(self.validator)

    def promote(
        self,
        sources: Iterable[Path | str],
        *,
        destination: Path | str,
        sqlite_path: Path | str | None = None,
    ) -> EvidenceCollection:
        """Validate ``sources`` and publish canonical artifacts."""

        collection = self.validator.validate_many(sources)
        target_path = Path(destination)
        if not target_path.parent.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
        dump_records(target_path, collection.records)
        if sqlite_path:
            self.indexer.build_sqlite(sources, sqlite_path=sqlite_path, collection=collection)
        return collection


__all__ = ["EvidencePromoter"]
