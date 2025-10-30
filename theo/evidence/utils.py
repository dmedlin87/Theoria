"""Shared helpers for the evidence toolkit."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

_RECORD_ADAPTER = TypeAdapter(list[dict[str, Any]])


def hash_sid(parts: Iterable[str]) -> str:
    """Generate a deterministic short identifier from ``parts``."""

    digest = hashlib.sha1()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()[:16]


def load_records(path: Path) -> tuple["EvidenceRecord", ...]:
    """Load evidence records from a JSON or JSONL file."""

    if path.suffix.lower() == ".jsonl":
        raw: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            raw.append(json.loads(line))
    else:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw = raw.get("records") or raw.get("data") or []
        if not isinstance(raw, list):
            raise TypeError(f"Expected list payload in {path}")
    payload = _RECORD_ADAPTER.validate_python(raw)
    from .models import EvidenceRecord  # late import to avoid cycles

    records = tuple(EvidenceRecord.model_validate(item) for item in payload)
    return records


def dump_records(path: Path, records: Sequence["EvidenceRecord"]) -> None:
    """Persist ``records`` as canonical JSON."""

    serializable = [record.model_dump(mode="json") for record in records]
    path.write_text(json.dumps(serializable, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


__all__ = ["hash_sid", "load_records", "dump_records"]
