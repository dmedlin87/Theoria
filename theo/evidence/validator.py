"""Validation utilities for evidence corpora."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .models import EvidenceCollection, EvidenceRecord
from .utils import load_records


class EvidenceValidator:
    """Validate one or more evidence files."""

    def __init__(self, base_path: Path | str | None = None) -> None:
        self.base_path = Path(base_path) if base_path else Path.cwd()

    def validate_file(self, path: Path | str) -> EvidenceCollection:
        """Validate a single evidence file and return the normalized collection."""

        resolved = self._resolve(path)
        if resolved.is_dir():
            msg = f"Expected an evidence file but received directory: {resolved}"
            raise IsADirectoryError(msg)
        records = load_records(resolved)
        collection = EvidenceCollection(records=records)
        return collection

    def validate_many(self, paths: Iterable[Path | str]) -> EvidenceCollection:
        """Validate multiple files and return a merged sorted collection."""

        merged: list[EvidenceRecord] = []
        for path in paths:
            resolved = self._resolve(path)
            targets = self._discover(resolved) if resolved.is_dir() else (resolved,)
            for target in targets:
                collection = self.validate_file(target)
                merged.extend(collection.records)

        # Deduplicate by SID to ensure deterministic downstream operations.
        unique: dict[str, EvidenceRecord] = {}
        for record in merged:
            if record.sid not in unique:
                unique[record.sid] = record

        return EvidenceCollection(records=tuple(unique.values()))

    def validate_all(self, directory: Path | str) -> EvidenceCollection:
        """Validate every JSON/JSONL/Markdown file in ``directory``."""

        resolved = self._resolve(directory)
        if not resolved.is_dir():
            msg = f"Expected a directory of evidence resources: {resolved}"
            raise NotADirectoryError(msg)
        files = self._discover(resolved)
        return self.validate_many(files)

    def _resolve(self, path: Path | str) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.base_path / candidate
        if not candidate.exists():
            msg = f"Evidence resource not found: {candidate}"
            raise FileNotFoundError(msg)
        return candidate

    def _discover(self, directory: Path) -> tuple[Path, ...]:
        files = sorted(
            (
                path
                for path in directory.iterdir()
                if path.is_file()
                and path.suffix.lower() in {".json", ".jsonl", ".md"}
            ),
            key=lambda item: item.name,
        )
        return tuple(files)


def validate(path: Path | str, *, base_path: Path | str | None = None) -> EvidenceCollection:
    """Convenience wrapper around :class:`EvidenceValidator`."""

    validator = EvidenceValidator(base_path=base_path)
    return validator.validate_file(path)


__all__ = ["EvidenceValidator", "validate"]
