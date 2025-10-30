"""Command line interface for the evidence toolkit."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import click

from .dossier import EvidenceDossier
from .indexer import EvidenceIndexer
from .promoter import EvidencePromoter
from .validator import EvidenceValidator


def _render_markdown(records: Iterable[dict[str, object]]) -> str:
    """Return a lightweight markdown dossier for ``records``."""

    lines: list[str] = ["# Evidence Dossier", ""]
    for record in records:
        title = str(record.get("title") or "Untitled evidence")
        sid = str(record.get("sid") or "")
        heading = f"## {title}"
        if sid:
            heading += f" ({sid})"
        lines.append(heading)
        normalized = record.get("normalized_osis") or record.get("osis") or ()
        if isinstance(normalized, Iterable) and not isinstance(normalized, (str, bytes)):
            osis = ", ".join(str(item) for item in normalized)
        else:
            osis = str(normalized)
        lines.append(f"- **Normalized OSIS:** {osis or 'N/A'}")
        tags = record.get("tags") or ()
        if isinstance(tags, Iterable) and not isinstance(tags, (str, bytes)):
            tag_list = ", ".join(str(tag) for tag in tags)
        else:
            tag_list = str(tags)
        lines.append(f"- **Tags:** {tag_list or 'N/A'}")
        summary = record.get("summary")
        if summary:
            lines.extend(["", str(summary)])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _render_graphviz(graph: dict[str, object]) -> str:
    """Render ``graph`` payload as a Graphviz DOT document."""

    nodes = list(map(str, graph.get("nodes", [])))
    edges = graph.get("edges", [])
    records = graph.get("records", [])
    lines = ["digraph Evidence {", "  rankdir=LR;"]
    for node in nodes:
        lines.append(f'  "{node}" [shape=box];')
    for record in records or []:
        sid = str(record.get("sid") or "")
        if sid:
            lines.append(f'  "{sid}" [shape=ellipse];')
    for edge in edges or []:
        osis = str(edge.get("osis") or "")
        for sid in edge.get("records", []):
            if osis and sid:
                lines.append(f'  "{osis}" -> "{sid}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


@click.group()
def cli() -> None:
    """Evidence management commands."""


@cli.command("validate")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
@click.option("--all", "validate_all", is_flag=True, help="Validate every file in a directory")
@click.option("--base-path", type=click.Path(path_type=Path), default=Path.cwd())
def validate_command(paths: tuple[Path, ...], validate_all: bool, base_path: Path) -> None:
    """Validate evidence payloads and emit normalized JSON."""

    validator = EvidenceValidator(base_path=base_path)
    if validate_all:
        if not paths:
            raise click.BadOptionUsage("--all", "Provide a directory to validate.")
        collection = validator.validate_all(paths[0])
    else:
        if not paths:
            raise click.UsageError("Provide at least one evidence file to validate.")
        collection = validator.validate_many(paths)
    click.echo(json.dumps([record.model_dump(mode="json") for record in collection.records], indent=2))


@cli.command("index")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
@click.option("--sqlite", "sqlite_path", required=True, type=click.Path(path_type=Path))
@click.option("--base-path", type=click.Path(path_type=Path), default=Path.cwd())
def index_command(paths: tuple[Path, ...], sqlite_path: Path, base_path: Path) -> None:
    """Build a SQLite index from evidence payloads."""

    if not paths:
        raise click.UsageError("Provide at least one evidence source file.")
    validator = EvidenceValidator(base_path=base_path)
    indexer = EvidenceIndexer(validator)
    collection = indexer.build_sqlite(paths, sqlite_path=sqlite_path)
    click.echo(f"Indexed {len(collection.records)} records into {sqlite_path}")


@cli.command("promote")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
@click.option("--output", "output_path", required=True, type=click.Path(path_type=Path))
@click.option("--sqlite", "sqlite_path", type=click.Path(path_type=Path))
@click.option("--base-path", type=click.Path(path_type=Path), default=Path.cwd())
def promote_command(
    paths: tuple[Path, ...],
    output_path: Path,
    sqlite_path: Path | None,
    base_path: Path,
) -> None:
    """Validate, normalize, and publish curated artifacts."""

    if not paths:
        raise click.UsageError("Provide at least one evidence file to promote.")
    validator = EvidenceValidator(base_path=base_path)
    promoter = EvidencePromoter(validator=validator)
    collection = promoter.promote(paths, destination=output_path, sqlite_path=sqlite_path)
    click.echo(f"Promoted {len(collection.records)} records to {output_path}")
    if sqlite_path:
        click.echo(f"SQLite index available at {sqlite_path}")


@cli.command("dossier")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
@click.option("--graph", "render_graph", is_flag=True, help="Emit a JSON graph of OSIS to evidence")
@click.option("--out", "output_path", type=click.Path(path_type=Path), help="Write the dossier to a file")
@click.option("--base-path", type=click.Path(path_type=Path), default=Path.cwd())
def dossier_command(
    paths: tuple[Path, ...],
    render_graph: bool,
    output_path: Path | None,
    base_path: Path,
) -> None:
    """Generate analytical dossiers for evidence collections."""

    if not paths:
        raise click.UsageError("Provide at least one evidence file.")
    validator = EvidenceValidator(base_path=base_path)
    dossier = EvidenceDossier(validator)
    if render_graph:
        graph = dossier.build_graph(paths)
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.suffix.lower() == ".dot":
                output_path.write_text(_render_graphviz(graph), encoding="utf-8")
            else:
                output_path.write_text(
                    json.dumps(graph, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
        else:
            click.echo(json.dumps(graph, indent=2))
    else:
        collection = validator.validate_many(paths)
        payload = [record.model_dump(mode="json") for record in collection.records]
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.suffix.lower() in {".md", ".markdown"}:
                output_path.write_text(_render_markdown(payload), encoding="utf-8")
            else:
                output_path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
        else:
            click.echo(json.dumps(payload, indent=2))


@cli.command("query")
@click.argument("sqlite_path", type=click.Path(path_type=Path))
@click.option("--osis", type=str)
@click.option("--tag", type=str)
def query_command(sqlite_path: Path, osis: str | None, tag: str | None) -> None:
    """Query a SQLite index for specific evidence."""

    indexer = EvidenceIndexer()
    results = indexer.query(sqlite_path, osis=osis, tag=tag)
    click.echo(json.dumps([record.model_dump(mode="json") for record in results], indent=2))


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    cli()


__all__ = ["cli"]
