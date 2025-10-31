"""Command line interface for the evidence toolkit."""

from __future__ import annotations

import json
from collections.abc import Iterable
import re
from pathlib import Path

import click

from .dossier import EvidenceDossier
from .indexer import EvidenceIndexer
from .promoter import EvidencePromoter
from .utils import dump_records_jsonl
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


CARDS_DIRECTORY = Path("evidence/cards")
REGISTRY_DIRECTORY = Path("evidence/registry")
DEFAULT_SQLITE_PATH = REGISTRY_DIRECTORY / "evidence.index.sqlite"
DEFAULT_JSONL_PATH = REGISTRY_DIRECTORY / "evidence.index.jsonl"


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
    default_target: Path | None = None if paths else CARDS_DIRECTORY
    if validate_all:
        directory = paths[0] if paths else default_target
        if directory is None:
            raise click.BadOptionUsage("--all", "Provide a directory to validate.")
        collection = validator.validate_all(directory)
    else:
        targets: tuple[Path, ...] = paths if paths else (default_target,) if default_target else ()
        if not targets:
            raise click.UsageError("Provide at least one evidence file to validate.")
        collection = validator.validate_many(targets)
    click.echo(json.dumps([record.model_dump(mode="json") for record in collection.records], indent=2))


@cli.command("index")
@click.argument("paths", nargs=-1, type=click.Path(path_type=Path))
@click.option(
    "--sqlite",
    "sqlite_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_SQLITE_PATH,
    show_default=True,
    help="Destination SQLite index path.",
)
@click.option(
    "--jsonl",
    "jsonl_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_JSONL_PATH,
    show_default=True,
    help="Destination JSONL registry path.",
)
@click.option("--base-path", type=click.Path(path_type=Path), default=Path.cwd())
def index_command(
    paths: tuple[Path, ...],
    sqlite_path: Path,
    jsonl_path: Path,
    base_path: Path,
) -> None:
    """Build a SQLite index from evidence payloads."""

    targets = paths if paths else (CARDS_DIRECTORY,)
    validator = EvidenceValidator(base_path=base_path)
    indexer = EvidenceIndexer(validator)
    collection = indexer.build_sqlite(targets, sqlite_path=sqlite_path)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    dump_records_jsonl(jsonl_path, collection.records)
    click.echo(
        f"Indexed {len(collection.records)} records into {sqlite_path} and {jsonl_path}"
    )


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
@click.option("--out", "out_path", type=click.Path(path_type=Path))
@click.option("--tags", "tags", multiple=True, help="Filter dossier records by tag")
@click.option(
    "--mode",
    type=click.Choice(["records", "summary", "full"], case_sensitive=False),
    default="records",
    show_default=True,
)
@click.option("--include-contradictions", is_flag=True, help="Include contradiction-tagged records")
@click.option(
    "--graph",
    "graph_format",
    type=click.Choice(["json", "dot"], case_sensitive=False),
    help="Generate an evidence graph in the requested format",
)
@click.option("--base-path", type=click.Path(path_type=Path), default=Path.cwd())
def dossier_command(
    paths: tuple[Path, ...],
    out_path: Path | None,
    tags: tuple[str, ...],
    mode: str,
    include_contradictions: bool,
    graph_format: str | None,
    base_path: Path,
) -> None:
    """Generate analytical dossiers for evidence collections."""

    validator = EvidenceValidator(base_path=base_path)
    dossier = EvidenceDossier(validator)
    targets = paths if paths else (CARDS_DIRECTORY,)

    tag_filters = _coerce_tags(tags)
    collection = dossier.collect(
        targets,
        tags=tag_filters if tag_filters else None,
        include_contradictions=include_contradictions,
    )

    mode_normalized = mode.lower()
    dossier_path: Path | None
    graph_path: Path | None
    dossier_path, graph_path = _resolve_output_paths(out_path, mode_normalized, graph_format)

    if dossier_path:
        dossier.export_dossier(
            dossier_path,
            mode=mode_normalized,
            tags=tag_filters if tag_filters else None,
            include_contradictions=include_contradictions,
            collection=collection,
        )
        click.echo(f"Wrote dossier to {dossier_path}")
    else:
        dossier_payload = dossier.build_dossier(
            targets,
            mode=mode_normalized,
            tags=tag_filters if tag_filters else None,
            include_contradictions=include_contradictions,
            collection=collection,
        )
        click.echo(json.dumps(dossier_payload, indent=2))

    if graph_format:
        if graph_path:
            dossier.export_graph(
                graph_path,
                format=graph_format.lower(),
                tags=tag_filters if tag_filters else None,
                include_contradictions=include_contradictions,
                collection=collection,
            )
            click.echo(f"Wrote graph to {graph_path}")
        else:
            graph_data = dossier.build_graph(
                targets,
                format=graph_format.lower(),
                tags=tag_filters if tag_filters else None,
                include_contradictions=include_contradictions,
                collection=collection,
            )
            if isinstance(graph_data, str):
                click.echo(graph_data)
            else:
                click.echo(json.dumps(graph_data, indent=2))


@cli.command("query")
@click.argument("sqlite_path", type=click.Path(path_type=Path))
@click.option("--osis", type=str)
@click.option("--tag", type=str)
def query_command(sqlite_path: Path, osis: str | None, tag: str | None) -> None:
    """Query a SQLite index for specific evidence."""

    indexer = EvidenceIndexer()
    results = indexer.query(sqlite_path, osis=osis, tag=tag)
    click.echo(json.dumps([record.model_dump(mode="json") for record in results], indent=2))


def _coerce_tags(values: tuple[str, ...]) -> tuple[str, ...]:
    tags: set[str] = set()
    for raw in values:
        if not raw:
            continue
        for item in re.split(r",|\s", raw):
            item = item.strip()
            if item:
                tags.add(item)
    return tuple(sorted(tags))


def _resolve_output_paths(
    out_path: Path | None, mode: str, graph_format: str | None
) -> tuple[Path | None, Path | None]:
    if out_path is None:
        return None, None

    target = Path(out_path)
    if target.suffix:
        dossier_path = target
        graph_path: Path | None = None
        if graph_format:
            suffix = ".dot" if graph_format.lower() == "dot" else ".json"
            graph_name = f"{dossier_path.stem}.graph{suffix}"
            graph_path = dossier_path.with_name(graph_name)
        return dossier_path, graph_path

    dossier_dir = target
    dossier_dir.mkdir(parents=True, exist_ok=True)
    dossier_path = dossier_dir / f"dossier.{mode}.json"
    graph_path = None
    if graph_format:
        suffix = "dot" if graph_format.lower() == "dot" else "json"
        graph_path = dossier_dir / f"graph.{suffix}"
    return dossier_path, graph_path


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    cli()


__all__ = ["cli"]
