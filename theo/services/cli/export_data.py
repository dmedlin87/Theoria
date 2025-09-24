"""CLI helpers for exporting content from Theo Engine."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Iterator

import click
from sqlalchemy.orm import Session

from ..api.app.core.database import get_engine
from ..api.app.models.export import DocumentExportFilters
from ..api.app.models.search import HybridSearchFilters, HybridSearchRequest
from ..api.app.retriever.export import export_documents, export_search_results


@contextmanager
def _session_scope() -> Iterator[Session]:
    engine = get_engine()
    with Session(engine) as session:
        yield session


def _write_json(obj: object, file) -> None:
    json.dump(obj, file, indent=2, ensure_ascii=False)
    file.write("\n")


def _write_ndjson(records: list[dict[str, object]], file) -> None:
    for record in records:
        file.write(json.dumps(record, ensure_ascii=False))
        file.write("\n")


@click.group()
def export() -> None:
    """Export content from the Theo Engine datastore."""


@export.command("search")
@click.option("--query", "q", type=str, default=None, help="Keyword query to run.")
@click.option("--osis", type=str, default=None, help="Optional OSIS reference filter.")
@click.option("--collection", type=str, default=None, help="Filter results to a collection.")
@click.option("--author", type=str, default=None, help="Filter results by author.")
@click.option("--source-type", type=str, default=None, help="Restrict to a source type.")
@click.option("--limit", "k", type=click.IntRange(1, 1000), default=100, show_default=True, help="Number of results to export.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "ndjson"], case_sensitive=False),
    default="json",
    show_default=True,
    help="Output format.",
)
@click.option("--output", type=click.File("w", encoding="utf-8"), default="-", help="File to write to (defaults to stdout).")
def export_search_command(
    *,
    q: str | None,
    osis: str | None,
    collection: str | None,
    author: str | None,
    source_type: str | None,
    k: int,
    output_format: str,
    output,
) -> None:
    """Export search results with their document metadata."""

    request = HybridSearchRequest(
        query=q,
        osis=osis,
        k=k,
        filters=HybridSearchFilters(collection=collection, author=author, source_type=source_type),
    )
    with _session_scope() as session:
        response = export_search_results(session, request)

    payload = response.model_dump(mode="json")
    if output_format.lower() == "json":
        _write_json(payload, output)
    else:
        header = {
            "kind": "metadata",
            "query": response.query,
            "osis": response.osis,
            "filters": response.filters.model_dump(mode="json"),
            "total_results": response.total_results,
        }
        rows = [header]
        for row in response.results:
            rows.append({"kind": "result", **row.model_dump(mode="json")})
        _write_ndjson(rows, output)


@export.command("documents")
@click.option("--collection", type=str, default=None, help="Collection to export.")
@click.option("--author", type=str, default=None, help="Filter documents by author.")
@click.option("--source-type", type=str, default=None, help="Restrict to a source type.")
@click.option("--limit", type=click.IntRange(1, 1000), default=None, help="Maximum number of documents to export.")
@click.option(
    "--include-passages/--no-include-passages",
    default=True,
    show_default=True,
    help="Include passages for each document.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "ndjson"], case_sensitive=False),
    default="json",
    show_default=True,
    help="Output format.",
)
@click.option("--output", type=click.File("w", encoding="utf-8"), default="-", help="File to write to (defaults to stdout).")
def export_documents_command(
    *,
    collection: str | None,
    author: str | None,
    source_type: str | None,
    limit: int | None,
    include_passages: bool,
    output_format: str,
    output,
) -> None:
    """Export documents and optionally their passages."""

    filters = DocumentExportFilters(collection=collection, author=author, source_type=source_type)
    with _session_scope() as session:
        response = export_documents(session, filters, include_passages=include_passages, limit=limit)

    payload = response.model_dump(mode="json")
    if output_format.lower() == "json":
        _write_json(payload, output)
    else:
        header = {
            "kind": "metadata",
            "filters": response.filters.model_dump(mode="json"),
            "include_passages": response.include_passages,
            "limit": response.limit,
            "total_documents": response.total_documents,
            "total_passages": response.total_passages,
        }
        rows = [header]
        for document in response.documents:
            rows.append({"kind": "document", **document.model_dump(mode="json")})
        _write_ndjson(rows, output)


if __name__ == "__main__":
    export()

