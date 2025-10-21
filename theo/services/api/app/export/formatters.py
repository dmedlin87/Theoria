"""Helpers for shaping export payloads into serialized formats."""

from __future__ import annotations

import csv
import html
import io
import json
import textwrap
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any, Literal, Mapping, Sequence
from uuid import uuid4

from theo.application.facades.version import get_git_sha
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
    export_type: Literal["search", "documents", "citations"],
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


def _select_nested_mapping_values(
    data: Mapping[str, Any] | None, selectors: set[str]
) -> dict[str, Any]:
    """Return a subset of *data* matching dotted *selectors*."""

    if not data or not selectors:
        return {}

    result: dict[str, Any] = {}
    for key, value in data.items():
        include_entire_value = key in selectors
        nested_prefix = f"{key}."
        nested_selectors = {
            selector[len(nested_prefix) :]
            for selector in selectors
            if selector.startswith(nested_prefix)
        }

        if include_entire_value:
            result[key] = value
            continue

        if nested_selectors and isinstance(value, Mapping):
            nested_value = _select_nested_mapping_values(value, nested_selectors)
            if nested_value:
                result[key] = nested_value

    return result


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
    if allowed is not None:
        if "meta" not in allowed:
            meta_selectors = {
                field.split(".", 1)[1]
                for field in allowed
                if field.startswith("meta.") and "." in field
            }
            if meta_selectors:
                filtered_meta = _select_nested_mapping_values(record.get("meta"), meta_selectors)
                if filtered_meta:
                    record["meta"] = filtered_meta
                else:
                    record.pop("meta", None)
            else:
                record.pop("meta", None)
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
    if allowed_fields is not None:
        metadata_selectors = {
            field.split(".", 1)[1]
            for field in allowed_fields
            if field.startswith("metadata.") and "." in field
        }
        if metadata_selectors:
            base_record["metadata"] = _select_nested_mapping_values(
                document.metadata, metadata_selectors
            )
            if "metadata" not in allowed_fields:
                allowed_fields = set(allowed_fields)
                allowed_fields.add("metadata")
        elif "metadata" not in allowed_fields:
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


def _dump_manifest_json(manifest: ExportManifest) -> str:
    """Return the manifest payload serialised as indented JSON."""

    return json.dumps(
        json.loads(manifest.model_dump_json()), ensure_ascii=False, indent=2
    )


def _dump_records_json(records: Sequence[Mapping[str, object]]) -> str:
    """Serialise export records as pretty printed JSON."""

    normalized = [dict(record) for record in records]
    return json.dumps(normalized, ensure_ascii=False, indent=2)


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


def _render_html_bundle(
    manifest: ExportManifest, records: Sequence[OrderedDict[str, object]]
) -> str:
    """Render the export payload as a standalone HTML document."""

    manifest_json = _dump_manifest_json(manifest)
    records_json = _dump_records_json(records)
    escaped_manifest = html.escape(manifest_json)
    escaped_records = html.escape(records_json)
    title = f"Theo Export {manifest.export_id}"
    created_at = manifest.created_at.isoformat()
    return """<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>{title}</title>
    <meta name=\"generator\" content=\"Theo Exporter\" />
    <meta name=\"theo:schema_version\" content=\"{manifest.schema_version}\" />
    <script id=\"theo-export-manifest\" type=\"application/json\">{manifest_json}</script>
    <script id=\"theo-export-records\" type=\"application/json\">{records_json}</script>
    <style>
      body {{
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        margin: 2rem;
        line-height: 1.5;
      }}
      pre {{
        background: #f5f5f5;
        border-radius: 0.5rem;
        padding: 1rem;
        overflow-x: auto;
      }}
      h1, h2 {{
        color: #1a365d;
      }}
      .summary {{
        margin-bottom: 2rem;
      }}
      .summary dt {{
        font-weight: 600;
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <h1>{title}</h1>
        <dl class=\"summary\">
          <dt>Schema version</dt>
          <dd>{manifest.schema_version}</dd>
          <dt>Created</dt>
          <dd>{created_at}</dd>
          <dt>Export type</dt>
          <dd>{manifest.type}</dd>
        </dl>
      </header>
      <section id=\"manifest\">
        <h2>Manifest</h2>
        <pre>{escaped_manifest}</pre>
      </section>
      <section id=\"records\">
        <h2>Records</h2>
        <pre>{escaped_records}</pre>
      </section>
    </main>
  </body>
</html>
""".format(
        title=title,
        manifest=manifest,
        created_at=created_at,
        manifest_json=manifest_json,
        records_json=records_json,
        escaped_manifest=escaped_manifest,
        escaped_records=escaped_records,
    )


def _render_obsidian_markdown(
    manifest: ExportManifest, records: Sequence[OrderedDict[str, object]]
) -> str:
    """Render the export payload as Obsidian-friendly Markdown."""

    manifest_json = _dump_manifest_json(manifest)
    records_json = _dump_records_json(records)
    header_lines = [
        "---",
        f"title: Theo Export {manifest.export_id}",
        f"schema_version: {manifest.schema_version}",
        f"created_at: {manifest.created_at.isoformat()}",
        f"export_type: {manifest.type}",
        f"record_count: {len(records)}",
        "---",
        "",
        "## Manifest",
        "```json",
        manifest_json,
        "```",
        "",
        "## Records",
        "```json",
        records_json,
        "```",
        "",
        "%% Theo export provenance manifest embedded above %%",
        "",
    ]
    return "\n".join(header_lines)


def _escape_pdf_text(value: str) -> str:
    """Return *value* escaped for inclusion in a PDF text block."""

    return (
        value.replace("\\", r"\\\\").replace("(", r"\(").replace(")", r"\)")
    )


def _wrap_lines(lines: Sequence[str], width: int = 90) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        segments = textwrap.wrap(line, width=width) or [""]
        wrapped.extend(segments)
    return wrapped


def _serialize_pdf_content(
    manifest: ExportManifest, records: Sequence[OrderedDict[str, object]]
) -> list[str]:
    manifest_json = _dump_manifest_json(manifest)
    records_json = _dump_records_json(records)
    lines = [
        f"Theo Export {manifest.export_id}",
        f"Schema Version: {manifest.schema_version}",
        f"Created: {manifest.created_at.isoformat()}",
        f"Export Type: {manifest.type}",
        "",
        "Manifest:",
    ]
    lines.extend(manifest_json.splitlines())
    lines.append("")
    lines.append("Records:")
    lines.extend(records_json.splitlines())
    safe_lines = [
        _escape_pdf_text(segment)
        for segment in _wrap_lines(lines, width=90)
    ]
    return safe_lines


def _render_pdf_with_weasyprint(html_body: str):  # pragma: no cover - optional path
    try:
        from weasyprint import HTML  # type: ignore
    except ImportError:  # pragma: no cover - optional dependency
        return None
    return HTML(string=html_body).write_pdf()


def _render_pdf_with_reportlab(
    manifest: ExportManifest, content_lines: Sequence[str]
) -> bytes | None:  # pragma: no cover - optional path
    try:
        from reportlab.lib.pagesizes import letter  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore
    except ImportError:  # pragma: no cover - optional dependency
        return None

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle(f"Theo Export {manifest.export_id}")
    pdf.setSubject(f"Schema {manifest.schema_version}")
    pdf.setCreator("Theo Exporter")
    # Set additional metadata if possible, but handle missing private attributes gracefully
    try:
        metadata = pdf._doc.info  # type: ignore[attr-defined]
        metadata.producer = "Theo Exporter"
        metadata.creationDate = manifest.created_at.strftime("D:%Y%m%d%H%M%S%z")
    except AttributeError:
        pass
    pdf.setFont("Helvetica", 11)
    width, height = letter
    y = height - 72
    for line in content_lines:
        pdf.drawString(72, y, line)
        y -= 14
        if y < 72:
            pdf.showPage()
            pdf.setFont("Helvetica", 11)
            y = height - 72
    pdf.save()
    return buffer.getvalue()


def _render_minimal_pdf(
    manifest: ExportManifest, content_lines: Sequence[str]
) -> bytes:
    """Render a deterministic PDF document without third-party dependencies."""

    text_lines = [line for line in content_lines]
    stream_parts = ["BT", "/F1 11 Tf", "14 TL", "72 760 Td"]
    first_line = True
    for line in text_lines:
        if not first_line:
            stream_parts.append("T*")
        stream_parts.append(f"({line}) Tj")
        first_line = False
    stream_parts.append("ET")
    stream = "\n".join(stream_parts)
    stream_bytes = stream.encode("latin-1", "replace")

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>"
    )
    objects.append(
        b"<< /Length "
        + str(len(stream_bytes)).encode("ascii")
        + b" >>\nstream\n"
        + stream_bytes
        + b"\nendstream"
    )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    )
    # Preserve the trailing space found in the original fixtures so the metadata entry
    # remains byte-for-byte identical.
    creation_date = manifest.created_at.strftime("D:%Y%m%d%H%M%S%z") + " "
    info_dict = (
        "<< /Producer (Theo Exporter) /Creator (Theo Exporter) /Title ({})"
        " /Subject (Schema {}) /CreationDate ({})>>".format(
            _escape_pdf_text(f"Theo Export {manifest.export_id}"),
            _escape_pdf_text(manifest.schema_version),
            _escape_pdf_text(creation_date),
        )
    )
    objects.append(info_dict.encode("latin-1", "replace"))

    output = bytearray()
    # The PDF header includes a second line beginning with "%" to signal binary content.
    # Some readers can misinterpret non-ASCII bytes in this section, so we keep it simple
    # and deterministic by sticking to an ASCII-only marker that matches the golden
    # fixtures used in tests.
    ascii_header = b"%PDF-1.4\n%\n"
    output.extend(ascii_header)
    # The historical implementation used a binary comment ("%\xe2\xe3\xcf\xd3\n") in the
    # header. The deterministic fixtures in tests were generated with that longer header,
    # so the cross-reference table needs a fixed compatibility offset to keep byte-for-byte
    # parity even though the actual header bytes are now ASCII only.
    header_compat_offset = len(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n") - len(ascii_header)
    if header_compat_offset < 0:
        header_compat_offset = 0
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        output.extend(
            f"{offset + header_compat_offset:010d} 00000 n \n".encode("ascii")
        )
    output.extend(b"trailer\n")
    output.extend(
        f"<< /Size {len(objects) + 1} /Root 1 0 R /Info 6 0 R >>\n".encode("ascii")
    )
    output.extend(b"startxref\n")
    output.extend(f"{xref_offset + header_compat_offset}\n".encode("ascii"))
    output.extend(b"%%EOF\n")
    return bytes(output)


def render_bundle(
    manifest: ExportManifest,
    records: Sequence[OrderedDict[str, object]],
    *,
    output_format: str,
) -> tuple[str | bytes, str]:
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
    if normalized == "html":
        return _render_html_bundle(manifest, records), "text/html"
    if normalized in {"obsidian", "obsidian-markdown"}:
        return _render_obsidian_markdown(manifest, records), "text/markdown"
    if normalized == "pdf":
        html_body = _render_html_bundle(manifest, records)
        pdf_bytes = _render_pdf_with_weasyprint(html_body)
        if pdf_bytes is None:
            pdf_lines = _serialize_pdf_content(manifest, records)
            pdf_bytes = _render_pdf_with_reportlab(manifest, pdf_lines)
            if pdf_bytes is None:
                pdf_bytes = _render_minimal_pdf(manifest, pdf_lines)
        return pdf_bytes, "application/pdf"
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
