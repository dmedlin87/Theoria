"""Helpers for shaping export payloads into serialized formats."""

from __future__ import annotations

import csv
import io
import json
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any, Literal, Mapping, Sequence
from uuid import uuid4

from ..core.version import get_git_sha
from ..models.base import Passage
from ..models.documents import DocumentDetailResponse
from ..models.export import DocumentExportResponse, ExportManifest, SearchExportResponse

SCHEMA_VERSION = "2024-07-01"
DEFAULT_FILENAME_PREFIX = "theo_export"

SEARCH_FIELD_ORDER: Sequence[str] = (
    "kind",
    "rank",
    "score",
    "document_id",
    "passage_id",
    "title",
    "collection",
    "source_type",
    "authors",
    "doi",
    "venue",
    "year",
    "topics",
    "primary_topic",
    "enrichment_version",
    "provenance_score",
    "osis_ref",
    "page_no",
    "t_start",
    "t_end",
    "snippet",
    "text",
)

DOCUMENT_FIELD_ORDER: Sequence[str] = (
    "kind",
    "document_id",
    "title",
    "collection",
    "source_type",
    "authors",
    "doi",
    "venue",
    "year",
    "topics",
    "primary_topic",
    "enrichment_version",
    "provenance_score",
    "abstract",
    "source_url",
    "metadata",
    "passages",
)

PASSAGE_FIELD_ORDER: Sequence[str] = (
    "id",
    "document_id",
    "osis_ref",
    "page_no",
    "t_start",
    "t_end",
    "text",
    "meta",
)


def generate_export_id() -> str:
    """Return a unique identifier for an export bundle."""

    return str(uuid4())


def build_manifest(
    *,
    export_type: Literal["search", "documents"],
    filters: Mapping[str, Any],
    totals: Mapping[str, Any],
    cursor: str | None,
    next_cursor: str | None,
    mode: str | None,
    enrichment_version: int | None,
    export_id: str | None = None,
) -> ExportManifest:
    """Create an :class:`ExportManifest` with common metadata."""

    manifest_id = export_id or generate_export_id()
    return ExportManifest(
        export_id=manifest_id,
        schema_version=SCHEMA_VERSION,
        created_at=datetime.now(UTC),
        type=export_type,
        filters=dict(filters),
        totals=dict(totals),
        app_git_sha=get_git_sha(),
        enrichment_version=enrichment_version,
        cursor=cursor,
        next_cursor=next_cursor,
        mode=mode,
    )


def _filter_values(
    record: dict, allowed: set[str] | None, order: Sequence[str]
) -> OrderedDict:
    """Filter *record* to include only keys listed in *allowed* preserving order."""

    expanded_allowed: set[str] | None = None
    if allowed is not None:
        expanded_allowed = set(allowed)
        for field in list(allowed):
            if "." not in field:
                continue
            parts = field.split(".")
            for index in range(1, len(parts)):
                expanded_allowed.add(".".join(parts[:index]))

    output: OrderedDict[str, object] = OrderedDict()
    for key in order:
        if key not in record:
            continue
        if expanded_allowed is not None and key not in expanded_allowed:
            continue
        value = record[key]
        if value is None and expanded_allowed is not None and key not in expanded_allowed:
            continue
        output[key] = value
    return output


def _passage_to_dict(
    passage: Passage, include_text: bool, allowed: set[str] | None
) -> OrderedDict:
    record = {
        "id": passage.id,
        "document_id": passage.document_id,
        "osis_ref": passage.osis_ref,
        "page_no": passage.page_no,
        "t_start": passage.t_start,
        "t_end": passage.t_end,
        "text": passage.text if include_text else None,
        "meta": passage.meta,
    }
    field_order = PASSAGE_FIELD_ORDER
    if not include_text and allowed is None:
        record.pop("text")
        field_order = tuple(key for key in PASSAGE_FIELD_ORDER if key != "text")
    if allowed is not None and "text" not in allowed and "passages.text" not in allowed:
        record.pop("text", None)
    return _filter_values(record, allowed, field_order)


def _search_row_to_record(
    response: SearchExportResponse,
    *,
    include_text: bool,
    fields: set[str] | None,
) -> list[OrderedDict[str, object]]:
    records: list[OrderedDict[str, object]] = []
    allowed_fields = set(fields) if fields else None
    include_text_field = include_text or (allowed_fields and ("text" in allowed_fields))

    mode = response.mode or "results"
    for row in response.results:
        passage = row.passage
        document = row.document
        snippet = row.snippet or (passage.meta.get("snippet") if passage.meta else None)
        base_record: dict[str, object] = {
            "kind": "mention" if mode == "mentions" else "result",
            "rank": row.rank,
            "score": row.score,
            "document_id": passage.document_id,
            "passage_id": passage.id,
            "title": document.title,
            "collection": document.collection,
            "source_type": document.source_type,
            "authors": document.authors,
            "doi": document.doi,
            "venue": document.venue,
            "year": document.year,
            "topics": document.topics,
            "primary_topic": document.primary_topic,
            "enrichment_version": document.enrichment_version,
            "provenance_score": document.provenance_score,
            "osis_ref": passage.osis_ref,
            "page_no": passage.page_no,
            "t_start": passage.t_start,
            "t_end": passage.t_end,
            "snippet": snippet or passage.text,
            "text": passage.text if include_text_field else None,
        }
        field_order = SEARCH_FIELD_ORDER
        if not include_text_field and allowed_fields is None:
            field_order = tuple(key for key in SEARCH_FIELD_ORDER if key != "text")
            base_record.pop("text")
        if allowed_fields is not None and "text" not in allowed_fields:
            base_record.pop("text", None)
        records.append(_filter_values(base_record, allowed_fields, field_order))
    return records


def _document_to_record(
    document: DocumentDetailResponse,
    *,
    include_passages: bool,
    include_text: bool,
    fields: set[str] | None,
) -> OrderedDict[str, object]:
    allowed_fields = set(fields) if fields else None
    base_record: dict[str, object] = {
        "kind": "document",
        "document_id": document.id,
        "title": document.title,
        "collection": document.collection,
        "source_type": document.source_type,
        "authors": document.authors,
        "doi": document.doi,
        "venue": document.venue,
        "year": document.year,
        "topics": document.topics,
        "primary_topic": document.primary_topic,
        "enrichment_version": document.enrichment_version,
        "provenance_score": document.provenance_score,
        "abstract": document.abstract,
        "source_url": document.source_url,
        "metadata": document.metadata,
    }
    field_order = DOCUMENT_FIELD_ORDER
    if include_passages:
        passage_fields = None
        if allowed_fields is not None:
            passage_fields = {
                key.split(".", 1)[1]
                for key in allowed_fields
                if key.startswith("passages.")
            }
            if "passages" not in allowed_fields and not passage_fields:
                include_passages = False
        if include_passages:
            include_passage_text = include_text
            if not include_passage_text and passage_fields:
                include_passage_text = any(
                    field == "text" or field.startswith("text.")
                    for field in passage_fields
                )
            base_record["passages"] = [
                dict(
                    _passage_to_dict(
                        passage,
                        include_passage_text,
                        passage_fields if passage_fields else None,
                    )
                )
                for passage in document.passages
            ]
    if not include_passages:
        base_record.pop("passages", None)
        field_order = tuple(key for key in DOCUMENT_FIELD_ORDER if key != "passages")
    if allowed_fields is not None and "metadata" not in allowed_fields:
        base_record.pop("metadata", None)
    return _filter_values(base_record, allowed_fields, field_order)


def build_search_export(
    response: SearchExportResponse,
    *,
    include_text: bool = False,
    fields: set[str] | None = None,
    export_id: str | None = None,
) -> tuple[ExportManifest, list[OrderedDict[str, object]]]:
    records = _search_row_to_record(response, include_text=include_text, fields=fields)
    enrichment_values = [
        row.document.enrichment_version
        for row in response.results
        if isinstance(row.document.enrichment_version, int)
    ]
    enrichment_version = max(enrichment_values) if enrichment_values else None
    manifest = build_manifest(
        export_type="search",
        filters={
            "query": response.query,
            "osis": response.osis,
            **response.filters.model_dump(mode="json"),
        },
        totals={"results": response.total_results, "returned": len(records)},
        cursor=response.cursor,
        next_cursor=response.next_cursor,
        mode=response.mode,
        enrichment_version=enrichment_version,
        export_id=export_id,
    )
    return manifest, records


def build_document_export(
    response: DocumentExportResponse,
    *,
    include_passages: bool,
    include_text: bool = False,
    fields: set[str] | None = None,
    export_id: str | None = None,
) -> tuple[ExportManifest, list[OrderedDict[str, object]]]:
    records = [
        _document_to_record(
            document,
            include_passages=include_passages,
            include_text=include_text,
            fields=fields,
        )
        for document in response.documents
    ]
    enrichment_values = [
        document.enrichment_version
        for document in response.documents
        if isinstance(document.enrichment_version, int)
    ]
    enrichment_version = max(enrichment_values) if enrichment_values else None
    manifest = build_manifest(
        export_type="documents",
        filters=response.filters.model_dump(mode="json"),
        totals={
            "documents": response.total_documents,
            "passages": response.total_passages,
            "returned": len(records),
        },
        cursor=response.cursor,
        next_cursor=response.next_cursor,
        mode=None,
        enrichment_version=enrichment_version,
        export_id=export_id,
    )
    return manifest, records


def render_json_bundle(manifest: ExportManifest, records: Sequence[dict]) -> str:
    payload = {
        "manifest": json.loads(manifest.model_dump_json()),
        "records": records,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_ndjson_bundle(manifest: ExportManifest, records: Sequence[dict]) -> str:
    lines = [manifest.model_dump_json()]
    for record in records:
        lines.append(json.dumps(record, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def render_csv_bundle(records: Sequence[OrderedDict[str, object]]) -> str:
    if not records:
        return ""
    header = list(records[0].keys())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header)
    writer.writeheader()
    for record in records:
        writer.writerow(record)
    return buffer.getvalue()


def render_bundle(
    manifest: ExportManifest,
    records: Sequence[OrderedDict[str, object]],
    *,
    output_format: str,
) -> tuple[str, str]:
    normalized = output_format.lower()
    if normalized == "json":
        return (
            render_json_bundle(manifest, [dict(row) for row in records]),
            "application/json",
        )
    if normalized == "ndjson":
        return (
            render_ndjson_bundle(manifest, [dict(row) for row in records]),
            "application/x-ndjson",
        )
    if normalized == "csv":
        csv_body = render_csv_bundle(records)
        body = manifest.model_dump_json() + "\n"
        if csv_body:
            body += csv_body
        return body, "text/csv"
    raise ValueError(f"Unsupported format: {output_format}")


__all__ = [
    "SCHEMA_VERSION",
    "DEFAULT_FILENAME_PREFIX",
    "build_document_export",
    "build_manifest",
    "build_search_export",
    "generate_export_id",
    "render_bundle",
    "render_csv_bundle",
    "render_json_bundle",
    "render_ndjson_bundle",
]
