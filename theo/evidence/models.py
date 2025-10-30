"""Pydantic models that define the evidence interchange format."""

from __future__ import annotations

import json

from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import citations, normalization
from .utils import hash_sid


class EvidenceCitation(BaseModel):
    """Represents a CSL citation reference used by an evidence record."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    citekey: str = Field(..., description="CSL citekey (Zotero-style identifier)")
    locator: str | None = Field(default=None, description="Citation locator such as a page range")
    note: str | None = Field(default=None, description="Optional citation note")

    @model_validator(mode="after")
    def _validate(self) -> "EvidenceCitation":
        if not citations.is_valid_csl_citekey(self.citekey):
            msg = "Invalid CSL citekey"
            raise ValueError(msg)
        return self


class EvidenceRecord(BaseModel):
    """Normalized unit of evidence linked to one or more OSIS references."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    title: str = Field(..., description="Human readable title for the evidence")
    summary: str | None = Field(default=None, description="Short description or excerpt")
    osis: tuple[str, ...] = Field(..., description="Input OSIS references supplied with the record")
    normalized_osis: tuple[str, ...] = Field(default=(), description="Canonical OSIS references")
    citation: EvidenceCitation | None = Field(default=None)
    tags: tuple[str, ...] = Field(default_factory=tuple)
    metadata: Mapping[str, Any] = Field(default_factory=dict)
    sid: str = Field(default="", description="Stable identifier generated from record content")

    _MIN_TITLE_LENGTH: ClassVar[int] = 3

    @field_validator("osis", mode="before")
    @classmethod
    def _coerce_osis(cls, value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, Iterable):
            raise TypeError("OSIS values must be iterable")
        items = [str(item).strip() for item in value if str(item).strip()]
        if not items:
            raise ValueError("At least one OSIS reference is required")
        return tuple(items)

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, Iterable):
            raise TypeError("Tags must be iterable of strings")
        tags = tuple(sorted({str(item).strip() for item in value if str(item).strip()}))
        return tags

    @model_validator(mode="after")
    def _finalize(self) -> "EvidenceRecord":
        if len(self.title) < self._MIN_TITLE_LENGTH:
            msg = "Title is too short"
            raise ValueError(msg)
        normalized = normalization.normalize_many(self.osis)
        if not normalized:
            msg = "Unable to normalize OSIS references"
            raise ValueError(msg)
        sid = self.sid or hash_sid(self._signature_parts(normalized))
        return self.model_copy(update={"normalized_osis": normalized, "sid": sid})

    def _signature_parts(self, normalized: tuple[str, ...]) -> tuple[str, ...]:
        """Derive stable signature components for SID generation."""

        citation = ""
        if self.citation:
            payload = self.citation.model_dump(mode="json", exclude_none=True)
            citation = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        metadata = json.dumps(
            _normalize_metadata(self.metadata),
            sort_keys=True,
            ensure_ascii=False,
        )
        parts = (
            self.title,
            "|".join(normalized),
            "|".join(self.osis),
            self.summary or "",
            citation,
            "|".join(self.tags),
            metadata,
        )
        return parts


class EvidenceCollection(BaseModel):
    """Container for deterministic ordering of evidence records."""

    model_config = ConfigDict(frozen=True)

    records: tuple[EvidenceRecord, ...] = Field(default=())

    @field_validator("records", mode="before")
    @classmethod
    def _coerce_records(cls, value: Any) -> tuple[EvidenceRecord, ...]:
        if value is None:
            return ()
        if isinstance(value, EvidenceRecord):
            return (value,)
        if isinstance(value, Iterable):
            records = tuple(EvidenceRecord.model_validate(item) for item in value)
            return records
        raise TypeError("records must be iterable")

    @model_validator(mode="after")
    def _sort(self) -> "EvidenceCollection":
        ordered = tuple(
            sorted(
                self.records,
                key=lambda record: (record.normalized_osis, record.sid),
            )
        )
        return self.model_copy(update={"records": ordered})


__all__ = ["EvidenceCitation", "EvidenceRecord", "EvidenceCollection"]


def _normalize_metadata(value: Any) -> Any:
    """Recursively coerce metadata to deterministic JSON-serializable forms."""

    if isinstance(value, Mapping):
        return {
            str(key): _normalize_metadata(val)
            for key, val in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_metadata(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_normalize_metadata(item) for item in value), key=_stable_repr)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return _stable_repr(value)


def _stable_repr(value: Any) -> str:
    """Generate a deterministic string representation for ``value``."""

    return repr(value)
