"""CLI helpers for exporting content from Theo Engine."""

from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Mapping, Sequence as SequenceABC
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Iterator, Sequence, cast

import click
from sqlalchemy import select
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import Document
from ..api.app.export.citations import build_citation_export, render_citation_markdown
from ..api.app.export.formatters import (
    build_document_export,
    build_search_export,
    generate_export_id,
    render_bundle,
)
from ..api.app.models.export import (
    CitationStyleLiteral,
    DocumentExportFilters,
    ExportManifest,
)
from ..api.app.models.search import HybridSearchFilters, HybridSearchRequest
from ..api.app.retriever.export import export_documents, export_search_results
from ..api.app.retriever.verses import get_mentions_for_osis
from ..api.app.models.verses import VerseMentionsFilters
from theo.services.bootstrap import resolve_application


APPLICATION_CONTAINER, _ADAPTER_REGISTRY = resolve_application()


def get_engine():  # pragma: no cover - transitional wiring helper
    return _ADAPTER_REGISTRY.resolve("engine")

STATE_DIR = Path(".export_state")


@contextmanager
def _session_scope() -> Iterator[Session]:
    engine = get_engine()
    with Session(engine) as session:
        yield session


def _parse_fields(fields: str | None) -> set[str] | None:
    if not fields:
        return None
    parsed = {item.strip() for item in fields.split(",") if item.strip()}
    return parsed or None


def _state_path(export_id: str) -> Path:
    return STATE_DIR / f"{export_id}.json"


def _load_saved_cursor(export_id: str) -> str | None:
    path = _state_path(export_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError:
        return None
    return data.get("next_cursor")


def _persist_state(manifest: ExportManifest) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _state_path(manifest.export_id)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(manifest.model_dump(mode="json"), fh, indent=2, ensure_ascii=False)
        fh.write("\n")


@contextmanager
def _open_output_stream(path: str, binary: bool) -> Iterator[IO[Any]]:
    """Yield a writable file handle for *path*, respecting binary formats."""

    if path == "-":
        stream = (
            click.get_binary_stream("stdout")
            if binary
            else click.get_text_stream("stdout")
        )
        yield stream
        return

    mode = "wb" if binary else "w"
    if binary:
        with open(path, mode) as handle:
            yield handle
    else:
        with open(path, mode, encoding="utf-8") as handle:
            yield handle


def _flatten_passages(
    records: Sequence[OrderedDict[str, object]],
) -> list[OrderedDict[str, object]]:
    flattened: list[OrderedDict[str, object]] = []
    for record in records:
        passages = record.get("passages") if isinstance(record, dict) else None
        if not passages:
            continue
        if not isinstance(passages, SequenceABC) or isinstance(passages, (str, bytes)):
            continue
        for passage in passages:
            if not isinstance(passage, Mapping):
                continue
            entry = OrderedDict()
            entry["kind"] = "passage"
            entry["document_id"] = record.get("document_id")
            entry["title"] = record.get("title")
            entry["collection"] = record.get("collection")
            entry["source_type"] = record.get("source_type")
            entry["passage_id"] = passage.get("id")
            entry["osis_ref"] = passage.get("osis_ref")
            entry["page_no"] = passage.get("page_no")
            entry["t_start"] = passage.get("t_start")
            entry["t_end"] = passage.get("t_end")
            if "text" in passage:
                entry["text"] = passage.get("text")
            entry["meta"] = passage.get("meta")
            flattened.append(entry)
    return flattened


def _format_anchor_label(passage) -> str | None:
    page_no = getattr(passage, "page_no", None)
    if isinstance(page_no, int):
        return f"p.{page_no}"
    t_start = getattr(passage, "t_start", None)
    t_end = getattr(passage, "t_end", None)
    if isinstance(t_start, (int, float)):
        if isinstance(t_end, (int, float)) and t_end != t_start:
            return f"{int(t_start)}-{int(t_end)}s"
        return f"{int(t_start)}s"
    return None


@click.group()
def export() -> None:
    """Export content from the Theo Engine datastore."""


@export.command("search")
@click.option("--query", "q", type=str, default=None, help="Keyword query to run.")
@click.option("--osis", type=str, default=None, help="Optional OSIS reference filter.")
@click.option(
    "--collection", type=str, default=None, help="Filter results to a collection."
)
@click.option("--author", type=str, default=None, help="Filter results by author.")
@click.option(
    "--source-type", type=str, default=None, help="Restrict to a source type."
)
@click.option(
    "--limit",
    type=click.IntRange(1, 1000),
    default=100,
    show_default=True,
    help="Number of results to export.",
)
@click.option(
    "--cursor", type=str, default=None, help="Resume from this passage identifier."
)
@click.option(
    "--fields",
    type=str,
    default=None,
    help="Comma separated list of fields to include.",
)
@click.option(
    "--include-text/--no-include-text",
    default=False,
    show_default=True,
    help="Include full passage text in each result row.",
)
@click.option(
    "--mode",
    type=click.Choice(["results", "mentions"], case_sensitive=False),
    default="results",
    show_default=True,
    help="Export regular results or verse mentions.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(
        ["json", "ndjson", "csv", "html", "pdf", "obsidian"],
        case_sensitive=False,
    ),
    default="ndjson",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--export-id", type=str, default=None, help="Identifier for resumable exports."
)
@click.option(
    "--metadata-only/--no-metadata-only",
    default=False,
    show_default=True,
    help="Write only the manifest without any result rows.",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, allow_dash=True, path_type=str),
    default="-",
    show_default=True,
    help="File path to write to (use '-' for stdout).",
)
def export_search_command(
    *,
    q: str | None,
    osis: str | None,
    collection: str | None,
    author: str | None,
    source_type: str | None,
    limit: int,
    cursor: str | None,
    fields: str | None,
    include_text: bool,
    mode: str,
    output_format: str,
    export_id: str | None,
    metadata_only: bool,
    output: str,
) -> None:
    """Export search results with their document metadata."""

    if mode.lower() == "mentions" and not osis:
        raise click.ClickException("mode=mentions requires an --osis argument")

    export_identifier = export_id or generate_export_id()
    if cursor is None and export_identifier:
        saved_cursor = _load_saved_cursor(export_identifier)
        if saved_cursor:
            cursor = saved_cursor

    fetch_k = limit + 1 if limit is not None else None
    request = HybridSearchRequest(
        query=q,
        osis=osis,
        k=fetch_k if fetch_k is not None else limit,
        limit=limit,
        cursor=cursor,
        mode=mode.lower(),
        filters=HybridSearchFilters(
            collection=collection, author=author, source_type=source_type
        ),
    )
    with _session_scope() as session:
        response = export_search_results(session, request)

    manifest, records = build_search_export(
        response,
        include_text=include_text,
        fields=_parse_fields(fields),
        export_id=export_identifier,
    )

    if metadata_only:
        records = []
        manifest.totals["returned"] = 0

    body, _ = render_bundle(manifest, records, output_format=output_format)
    binary_payload = isinstance(body, (bytes, bytearray))
    with _open_output_stream(output, binary=binary_payload) as stream:
        if binary_payload:
            stream.write(body)  # type: ignore[arg-type]
        else:
            stream.write(body)
            if not body.endswith("\n"):
                stream.write("\n")
    _persist_state(manifest)


@export.command("citations")
@click.option(
    "--style",
    type=click.Choice([
        "apa",
        "chicago",
        "sbl",
        "bibtex",
        "csl-json",
    ], case_sensitive=False),
    default="apa",
    show_default=True,
    help="Citation style to render.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(
        ["markdown", "json", "ndjson", "csv", "html", "pdf", "obsidian"],
        case_sensitive=False,
    ),
    default="markdown",
    show_default=True,
    help="Output format for the citation bundle.",
)
@click.option(
    "--document-id",
    "document_ids",
    type=str,
    multiple=True,
    help="Document identifier to include (may be repeated).",
)
@click.option("--osis", type=str, default=None, help="OSIS reference to collect mentions for.")
@click.option("--collection", type=str, default=None, help="Filter mentions by collection.")
@click.option("--author", type=str, default=None, help="Filter mentions by author.")
@click.option("--source-type", type=str, default=None, help="Filter mentions by source type.")
@click.option(
    "--limit",
    type=click.IntRange(1, 1000),
    default=None,
    help="Maximum number of verse mentions to inspect.",
)
@click.option("--export-id", type=str, default=None, help="Optional export identifier.")
@click.option(
    "--output",
    type=click.Path(dir_okay=False, allow_dash=True, path_type=str),
    default="-",
    show_default=True,
    help="File path to write to (use '-' for stdout).",
)
def export_citations_command(
    *,
    style: str,
    output_format: str,
    document_ids: tuple[str, ...],
    osis: str | None,
    collection: str | None,
    author: str | None,
    source_type: str | None,
    limit: int | None,
    export_id: str | None,
    output: str,
) -> None:
    """Render citations for explicit documents or verse aggregator results."""

    normalized_style = style.lower()
    normalized_format = output_format.lower()
    filters = DocumentExportFilters(
        collection=collection, author=author, source_type=source_type
    )

    ordered_ids: list[str] = []
    seen: set[str] = set()
    for candidate in document_ids:
        doc_id = candidate.strip()
        if not doc_id or doc_id in seen:
            continue
        ordered_ids.append(doc_id)
        seen.add(doc_id)

    anchor_map: dict[str, list[dict[str, Any]]] = {}

    with _session_scope() as session:
        if osis:
            verse_filters = VerseMentionsFilters(
                source_type=source_type, collection=collection, author=author
            )
            mentions = get_mentions_for_osis(session, osis, verse_filters)
            if limit is not None:
                mentions = mentions[:limit]
            for mention in mentions:
                doc_id = mention.passage.document_id
                if doc_id not in seen:
                    ordered_ids.append(doc_id)
                    seen.add(doc_id)
                anchors = anchor_map.setdefault(doc_id, [])
                label = _format_anchor_label(mention.passage)
                anchors.append(
                    {
                        "osis": mention.passage.osis_ref or osis,
                        "label": label,
                        "snippet": mention.context_snippet,
                        "passage_id": mention.passage.id,
                        "page_no": mention.passage.page_no,
                        "t_start": mention.passage.t_start,
                        "t_end": mention.passage.t_end,
                    }
                )

        if not ordered_ids:
            raise click.ClickException("No documents matched the requested selection.")

        rows = session.execute(
            select(Document).where(Document.id.in_(ordered_ids))
        ).scalars()
        document_index = {row.id: row for row in rows}
        missing = [doc_id for doc_id in ordered_ids if doc_id not in document_index]
        if missing:
            raise click.ClickException(
                f"Unknown document(s): {', '.join(sorted(missing))}"
            )
        documents = [document_index[doc_id] for doc_id in ordered_ids]

    filter_payload = filters.model_dump(exclude_none=True)
    if osis:
        filter_payload["osis"] = osis

    manifest, records, _ = build_citation_export(
        documents,
        style=cast(CitationStyleLiteral, normalized_style),
        anchors=anchor_map,
        filters=filter_payload,
        export_id=export_id,
    )

    if normalized_format == "markdown":
        body = render_citation_markdown(manifest, records)
        with _open_output_stream(output, binary=False) as stream:
            stream.write(body)
            if not body.endswith("\n"):
                stream.write("\n")
    else:
        body, _ = render_bundle(manifest, records, output_format=normalized_format)
        binary_payload = isinstance(body, (bytes, bytearray))
        with _open_output_stream(output, binary=binary_payload) as stream:
            if binary_payload:
                stream.write(body)  # type: ignore[arg-type]
            else:
                stream.write(body)
                if not body.endswith("\n"):
                    stream.write("\n")


@export.command("documents")
@click.option("--collection", type=str, default=None, help="Collection to export.")
@click.option("--author", type=str, default=None, help="Filter documents by author.")
@click.option(
    "--source-type", type=str, default=None, help="Restrict to a source type."
)
@click.option(
    "--limit",
    type=click.IntRange(1, 1000),
    default=None,
    help="Maximum number of documents to export.",
)
@click.option(
    "--include-passages/--no-include-passages",
    default=True,
    show_default=True,
    help="Include passages for each document.",
)
@click.option(
    "--include-text/--no-include-text",
    default=False,
    show_default=True,
    help="Include passage text when passages are exported.",
)
@click.option(
    "--cursor", type=str, default=None, help="Resume from this document identifier."
)
@click.option(
    "--fields",
    type=str,
    default=None,
    help="Comma separated list of fields to include.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "ndjson", "html", "pdf", "obsidian"], case_sensitive=False),
    default="ndjson",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--export-id", type=str, default=None, help="Identifier for resumable exports."
)
@click.option(
    "--metadata-only/--no-metadata-only",
    default=False,
    show_default=True,
    help="Export only document metadata (no passages).",
)
@click.option(
    "--passages-only/--no-passages-only",
    default=False,
    show_default=True,
    help="Emit only passage rows for each document.",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, allow_dash=True, path_type=str),
    default="-",
    show_default=True,
    help="File path to write to (use '-' for stdout).",
)
def export_documents_command(
    *,
    collection: str | None,
    author: str | None,
    source_type: str | None,
    limit: int | None,
    include_passages: bool,
    include_text: bool,
    cursor: str | None,
    fields: str | None,
    output_format: str,
    export_id: str | None,
    metadata_only: bool,
    passages_only: bool,
    output: str,
) -> None:
    """Export documents and optionally their passages."""

    if metadata_only:
        include_passages = False
    if passages_only and not include_passages:
        raise click.ClickException("--passages-only requires passages to be included")
    export_identifier = export_id or generate_export_id()
    if cursor is None and export_identifier:
        saved_cursor = _load_saved_cursor(export_identifier)
        if saved_cursor:
            cursor = saved_cursor

    filters = DocumentExportFilters(
        collection=collection, author=author, source_type=source_type
    )
    with _session_scope() as session:
        response = export_documents(
            session,
            filters,
            include_passages=include_passages,
            limit=limit,
            cursor=cursor,
        )

    manifest, records = build_document_export(
        response,
        include_passages=include_passages,
        include_text=include_text,
        fields=_parse_fields(fields),
        export_id=export_identifier,
    )

    if passages_only:
        records = _flatten_passages(records)

    body, _ = render_bundle(manifest, records, output_format=output_format)
    binary_payload = isinstance(body, (bytes, bytearray))
    with _open_output_stream(output, binary=binary_payload) as stream:
        if binary_payload:
            stream.write(body)  # type: ignore[arg-type]
        else:
            stream.write(body)
            if not body.endswith("\n"):
                stream.write("\n")
    _persist_state(manifest)


if __name__ == "__main__":
    export()
