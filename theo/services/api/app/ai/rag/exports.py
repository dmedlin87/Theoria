"""Export assembly helpers for RAG workflows."""

from __future__ import annotations

import json
import textwrap
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from theo.application.facades.version import get_git_sha
from theo.services.api.app.persistence_models import Document, Passage

from ...export.formatters import SCHEMA_VERSION, generate_export_id
from ...models.export import DeliverableAsset, DeliverableManifest, DeliverablePackage
from .guardrail_helpers import (
    GuardrailError,
    sanitize_json_structure,
    sanitize_markdown_field,
)

_SUPPORTED_DELIVERABLE_FORMATS = {"markdown", "ndjson", "csv", "pdf"}


def normalise_formats(formats: Sequence[str]) -> list[str]:
    """Return a deduplicated list of valid deliverable formats."""

    normalised: list[str] = []
    for fmt in formats:
        candidate = fmt.lower()
        if candidate not in _SUPPORTED_DELIVERABLE_FORMATS:
            raise ValueError(f"Unsupported format: {fmt}")
        if candidate not in normalised:
            normalised.append(candidate)
    return normalised


def build_deliverable_manifest(
    deliverable_type: str,
    *,
    export_id: str | None = None,
    filters: Mapping[str, Any] | None = None,
    model_preset: str | None = None,
    sources: Sequence[str] | None = None,
) -> DeliverableManifest:
    """Create a manifest describing the generated deliverable."""

    manifest_sources = list(dict.fromkeys(list(sources or [])))
    return DeliverableManifest(
        export_id=export_id or generate_export_id(),
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(UTC),
        type=deliverable_type,  # type: ignore[arg-type]
        filters=dict(filters or {}),
        git_sha=get_git_sha(),
        model_preset=model_preset,
        sources=manifest_sources,
    )


def _manifest_front_matter(manifest: DeliverableManifest) -> list[str]:
    lines = [
        "---",
        f"export_id: {sanitize_markdown_field(manifest.export_id)}",
        f"schema_version: {sanitize_markdown_field(manifest.schema_version)}",
        f"generated_at: {sanitize_markdown_field(manifest.generated_at.isoformat())}",
        f"type: {sanitize_markdown_field(manifest.type)}",
    ]
    if manifest.model_preset:
        lines.append(f"model_preset: {sanitize_markdown_field(manifest.model_preset)}")
    if manifest.git_sha:
        lines.append(f"git_sha: {sanitize_markdown_field(manifest.git_sha)}")
    if manifest.sources:
        sources = sanitize_json_structure(list(manifest.sources))
        lines.append(f"sources: {json.dumps(sources, ensure_ascii=False)}")
    if manifest.filters:
        filters = sanitize_json_structure(dict(manifest.filters))
        lines.append(
            f"filters: {json.dumps(filters, sort_keys=True, ensure_ascii=False)}"
        )
    lines.append("---\n")
    return lines


def _csv_manifest_prefix(manifest: DeliverableManifest) -> str:
    parts = [
        f"export_id={manifest.export_id}",
        f"schema_version={manifest.schema_version}",
        f"generated_at={manifest.generated_at.isoformat()}",
        f"type={manifest.type}",
    ]
    if manifest.model_preset:
        parts.append(f"model_preset={manifest.model_preset}")
    if manifest.git_sha:
        parts.append(f"git_sha={manifest.git_sha}")
    if manifest.sources:
        parts.append(f"sources={json.dumps(manifest.sources)}")
    if manifest.filters:
        parts.append(f"filters={json.dumps(manifest.filters, sort_keys=True)}")
    return ",".join(parts) + "\n"


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _markdown_to_pdf_lines(markdown: str) -> list[str]:
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            lines.append(heading.upper() if heading else "")
            lines.append("")
            continue
        prefix = ""
        content = stripped
        if stripped.startswith(("- ", "* ")):
            prefix = "• "
            content = stripped[2:].strip()
        wrapped = textwrap.wrap(content, width=90) or [""]
        for idx, item in enumerate(wrapped):
            if prefix and idx == 0:
                lines.append(f"{prefix}{item}")
            elif prefix:
                lines.append(f"{' ' * len(prefix)}{item}")
            else:
                lines.append(item)
    return lines or [""]


def _render_markdown_pdf(markdown: str, *, title: str | None = None) -> bytes:
    text_lines = _markdown_to_pdf_lines(markdown)
    heading_lines: list[str] = []
    if title:
        clean_title = title.strip()
        if clean_title:
            heading_lines = [clean_title, ""]
    combined = heading_lines + text_lines
    if not combined:
        combined = [""]

    commands = [
        "BT",
        "/F1 12 Tf",
        "16 TL",
        "72 756 Td",
    ]
    for idx, line in enumerate(combined):
        commands.append(f"({_escape_pdf_text(line)}) Tj")
        if idx != len(combined) - 1:
            commands.append("T*")
    commands.append("ET")
    stream = "\n".join(commands).encode("utf-8")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        if not obj.endswith(b"\n"):
            pdf.extend(b"\n")
        pdf.extend(b"endobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(b"trailer\n")
    pdf.extend(f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii"))
    pdf.extend(b"startxref\n")
    pdf.extend(f"{xref_offset}\n".encode("ascii"))
    pdf.extend(b"%%EOF\n")
    return bytes(pdf)


def _render_sermon_markdown(
    manifest: DeliverableManifest, response: "SermonPrepResponse"
) -> str:
    lines = _manifest_front_matter(manifest)
    lines.append(
        f"# Sermon Prep — {sanitize_markdown_field(response.topic)}"
    )
    if response.osis:
        lines.append(
            f"Focus Passage: {sanitize_markdown_field(response.osis)}\n"
        )
    if response.outline:
        lines.append("## Outline")
        for item in response.outline:
            lines.append(f"- {sanitize_markdown_field(item)}")
        lines.append("")
    if response.key_points:
        lines.append("## Key Points")
        for point in response.key_points:
            lines.append(f"- {sanitize_markdown_field(point)}")
        lines.append("")
    if response.answer.citations:
        lines.append("## Citations")
        for citation in response.answer.citations:
            osis = sanitize_markdown_field(citation.osis)
            anchor = sanitize_markdown_field(citation.anchor)
            snippet = sanitize_markdown_field(citation.snippet)
            lines.append(f"- {osis} ({anchor}) — {snippet}")
    return "\n".join(lines).strip() + "\n"


def _render_sermon_ndjson(
    manifest: DeliverableManifest, response: "SermonPrepResponse"
) -> str:
    payload = manifest.model_dump(mode="json")
    lines = [json.dumps(payload, ensure_ascii=False)]
    for idx, item in enumerate(response.outline, start=1):
        lines.append(
            json.dumps(
                {"kind": "outline", "order": idx, "value": item},
                ensure_ascii=False,
            )
        )
    for idx, point in enumerate(response.key_points, start=1):
        lines.append(
            json.dumps(
                {"kind": "key_point", "order": idx, "value": point},
                ensure_ascii=False,
            )
        )
    for citation in response.answer.citations:
        lines.append(
            json.dumps(
                {
                    "kind": "citation",
                    "osis": citation.osis,
                    "anchor": citation.anchor,
                    "snippet": citation.snippet,
                    "document_id": citation.document_id,
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines) + "\n"


def _render_sermon_csv(
    manifest: DeliverableManifest, response: "SermonPrepResponse"
) -> str:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=["osis", "anchor", "snippet", "document_id"]
    )
    writer.writeheader()
    for citation in response.answer.citations:
        writer.writerow(
            {
                "osis": citation.osis,
                "anchor": citation.anchor,
                "snippet": citation.snippet,
                "document_id": citation.document_id,
            }
        )
    return _csv_manifest_prefix(manifest) + buffer.getvalue()


def _render_sermon_pdf(
    manifest: DeliverableManifest, response: "SermonPrepResponse"
) -> bytes:
    markdown = _render_sermon_markdown(manifest, response)
    title = f"Sermon Prep — {response.topic}" if response.topic else None
    return _render_markdown_pdf(markdown, title=title)


def build_sermon_deliverable(
    response: "SermonPrepResponse",
    *,
    formats: Sequence[str],
    filters: Mapping[str, Any] | None = None,
) -> DeliverablePackage:
    """Render sermon prep content as a multi-format deliverable."""

    from .models import SermonPrepResponse

    if not isinstance(response, SermonPrepResponse):
        raise TypeError("response must be a SermonPrepResponse")

    normalised = normalise_formats(formats)
    citations = response.answer.citations
    export_id = (
        f"sermon-{citations[0].document_id}"
        if citations
        else generate_export_id()
    )
    manifest_filters: dict[str, Any] = {"topic": response.topic}
    if response.osis:
        manifest_filters["osis"] = response.osis
    if filters:
        manifest_filters["search_filters"] = dict(filters)
    manifest = build_deliverable_manifest(
        "sermon",
        export_id=export_id,
        filters=manifest_filters,
        model_preset=response.answer.model_name,
        sources=[citation.document_id for citation in citations],
    )
    assets: list[DeliverableAsset] = []
    for fmt in normalised:
        if fmt == "markdown":
            body = _render_sermon_markdown(manifest, response)
            media_type = "text/markdown"
            filename = "sermon.md"
        elif fmt == "ndjson":
            body = _render_sermon_ndjson(manifest, response)
            media_type = "application/x-ndjson"
            filename = "sermon.ndjson"
        elif fmt == "csv":
            body = _render_sermon_csv(manifest, response)
            media_type = "text/csv"
            filename = "sermon.csv"
        elif fmt == "pdf":
            body = _render_sermon_pdf(manifest, response)
            media_type = "application/pdf"
            filename = "sermon.pdf"
        else:  # pragma: no cover - guarded earlier
            raise ValueError(f"Unsupported format: {fmt}")
        assets.append(
            DeliverableAsset(
                format=fmt,
                filename=filename,
                media_type=media_type,
                content=body,
            )
        )
    return DeliverablePackage(manifest=manifest, assets=assets)


def _build_transcript_rows(passages: Sequence[Passage]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for passage in passages:
        speaker = None
        if passage.meta and isinstance(passage.meta, dict):
            speaker = passage.meta.get("speaker")
        rows.append(
            {
                "speaker": speaker or "Narrator",
                "text": passage.text,
                "osis": passage.osis_ref,
                "t_start": passage.t_start,
                "t_end": passage.t_end,
                "page_no": passage.page_no,
                "passage_id": passage.id,
            }
        )
    return rows


def _render_transcript_markdown(
    manifest: DeliverableManifest,
    title: str | None,
    rows: Sequence[dict[str, Any]],
) -> str:
    lines = _manifest_front_matter(manifest)
    heading_subject = title or manifest.filters.get("document_id") or ""
    lines.append(
        f"# Q&A Transcript — {sanitize_markdown_field(heading_subject)}"
    )
    for row in rows:
        anchor = row.get("osis") or row.get("page_no") or row.get("t_start")
        speaker = sanitize_markdown_field(row.get("speaker"))
        anchor_text = sanitize_markdown_field(anchor)
        text = sanitize_markdown_field(row.get("text"))
        lines.append(f"- **{speaker}** ({anchor_text}): {text}")
    return "\n".join(lines).strip() + "\n"


def _render_transcript_ndjson(
    manifest: DeliverableManifest, rows: Sequence[dict[str, Any]]
) -> str:
    payload = manifest.model_dump(mode="json")
    lines = [json.dumps(payload, ensure_ascii=False)]
    for row in rows:
        lines.append(json.dumps(row, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def _render_transcript_csv(
    manifest: DeliverableManifest, rows: Sequence[dict[str, Any]]
) -> str:
    import csv
    import io

    buffer = io.StringIO()
    fieldnames = list(rows[0].keys()) if rows else ["speaker", "text"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return _csv_manifest_prefix(manifest) + buffer.getvalue()


def _render_transcript_pdf(
    manifest: DeliverableManifest,
    title: str | None,
    rows: Sequence[dict[str, Any]],
) -> bytes:
    markdown = _render_transcript_markdown(manifest, title, rows)
    heading = f"Transcript — {title}" if title else "Transcript"
    return _render_markdown_pdf(markdown, title=heading)


def build_transcript_deliverable(
    session: Session,
    document_id: str,
    *,
    formats: Sequence[str],
) -> DeliverablePackage:
    """Generate transcript exports for the requested document."""

    document = session.get(Document, document_id)
    if document is None:
        raise GuardrailError(
            f"Document {document_id} not found",
            metadata={
                "code": "ingest_document_missing",
                "guardrail": "ingest",
                "suggested_action": "upload",
                "reason": document_id,
            },
        )
    passages = (
        session.query(Passage)
        .filter(Passage.document_id == document_id)
        .order_by(
            Passage.page_no.asc(),
            Passage.t_start.asc(),
            Passage.start_char.asc(),
        )
        .all()
    )
    rows = _build_transcript_rows(passages)
    manifest = build_deliverable_manifest(
        "transcript",
        export_id=f"transcript-{document_id}",
        filters={"document_id": document_id},
        sources=[document_id],
    )
    normalised = normalise_formats(formats)
    assets: list[DeliverableAsset] = []
    for fmt in normalised:
        if fmt == "markdown":
            body = _render_transcript_markdown(manifest, document.title, rows)
            media_type = "text/markdown"
            filename = "transcript.md"
        elif fmt == "ndjson":
            body = _render_transcript_ndjson(manifest, rows)
            media_type = "application/x-ndjson"
            filename = "transcript.ndjson"
        elif fmt == "csv":
            body = _render_transcript_csv(manifest, rows)
            media_type = "text/csv"
            filename = "transcript.csv"
        elif fmt == "pdf":
            body = _render_transcript_pdf(manifest, document.title, rows)
            media_type = "application/pdf"
            filename = "transcript.pdf"
        else:  # pragma: no cover - guarded earlier
            raise ValueError(f"Unsupported format: {fmt}")
        assets.append(
            DeliverableAsset(
                format=fmt,
                filename=filename,
                media_type=media_type,
                content=body,
            )
        )
    return DeliverablePackage(manifest=manifest, assets=assets)


def build_sermon_prep_package(
    response: "SermonPrepResponse", *, format: str
) -> tuple[str | bytes, str]:
    normalised = format.lower()
    package = build_sermon_deliverable(response, formats=[normalised])
    asset = package.get_asset(normalised)
    return asset.content, asset.media_type


def build_transcript_package(
    session: Session,
    document_id: str,
    *,
    format: str,
) -> tuple[str | bytes, str]:
    normalised = format.lower()
    package = build_transcript_deliverable(session, document_id, formats=[normalised])
    asset = package.get_asset(normalised)
    return asset.content, asset.media_type


__all__ = [
    "DeliverableAsset",
    "DeliverableManifest",
    "DeliverablePackage",
    "GuardrailError",
    "build_deliverable_manifest",
    "build_sermon_deliverable",
    "build_sermon_prep_package",
    "build_transcript_deliverable",
    "build_transcript_package",
    "normalise_formats",
]
