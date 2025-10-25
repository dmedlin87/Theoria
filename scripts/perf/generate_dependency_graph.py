#!/usr/bin/env python3
"""Generate dependency graph artifacts for the Theo package.

The script uses :mod:`grimp` to inspect import relationships within the
configured packages (``theo`` by default) and emits both JSON metadata and an
SVG visualisation into ``dashboard/dependency-graph``. The generated files are
intended to be checked into version control so architecture drift can be
tracked over time.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

try:
    import grimp
except ImportError as exc:  # pragma: no cover - fail fast when dependency is missing
    raise SystemExit(
        "grimp is required to build the dependency graph. "
        "Install it with `pip install grimp` and re-run the script."
    ) from exc


@dataclass(frozen=True)
class Edge:
    importer: str
    imported: str


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate dependency graph artefacts.")
    parser.add_argument(
        "--package",
        action="append",
        dest="packages",
        default=None,
        help="Package name(s) to analyse. Can be provided multiple times."
        " Defaults to just 'theo'.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory where JSON and SVG output files will be written."
        " Defaults to <repo>/dashboard/dependency-graph.",
    )
    parser.add_argument(
        "--svg-name",
        default="dependency-graph.svg",
        help="Filename for the generated SVG diagram.",
    )
    parser.add_argument(
        "--json-name",
        default="dependency-graph.json",
        help="Filename for the generated JSON metadata.",
    )
    parser.add_argument(
        "--dot-name",
        default=None,
        help="Optional filename for persisting the intermediate DOT source.",
    )
    parser.add_argument(
        "--include-external",
        action="store_true",
        help="Include imports to external packages in the graph (defaults to internal only).",
    )
    namespace = parser.parse_args(argv)
    if not namespace.packages:
        namespace.packages = ["theo"]
    return namespace


def determine_project_root() -> Path:
    script_path = Path(__file__).resolve()
    try:
        return script_path.parents[2]
    except IndexError:  # pragma: no cover - defensive guard for unexpected layouts
        return script_path.parent


def build_graph(packages: Iterable[str], include_external: bool) -> "grimp.ImportGraph":
    packages = list(dict.fromkeys(packages))  # preserve order but ensure uniqueness
    if not packages:
        raise SystemExit("At least one package must be provided via --package.")

    first, *rest = packages
    return grimp.build_graph(
        first,
        *rest,
        include_external_packages=include_external,
        exclude_type_checking_imports=True,
    )


def collect_edges(graph: "grimp.ImportGraph") -> list[Edge]:
    modules = sorted(graph.modules)
    edges: list[Edge] = []
    module_set = set(modules)

    for importer in modules:
        imported_modules = graph.find_modules_directly_imported_by(importer)
        for imported in imported_modules:
            if imported not in module_set:
                continue
            edges.append(Edge(importer=importer, imported=imported))

    edges.sort(key=lambda edge: (edge.importer, edge.imported))
    return edges


def serialise_json(
    packages: Sequence[str],
    modules: Sequence[str],
    edges: Sequence[Edge],
    destination: Path,
) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packages": list(packages),
        "module_count": len(modules),
        "edge_count": len(edges),
        "modules": list(modules),
        "edges": [edge.__dict__ for edge in edges],
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=False))


def build_dot(modules: Sequence[str], edges: Sequence[Edge]) -> str:
    lines = [
        "digraph theo_dependencies {",
        "  rankdir=LR;",
        "  node [shape=box, fontname=\"Helvetica\", fontsize=10];",
    ]

    for module in modules:
        lines.append(f'  "{module}";')

    for edge in edges:
        lines.append(f'  "{edge.importer}" -> "{edge.imported}";')

    lines.append("}")
    return "\n".join(lines) + "\n"


def render_svg(dot_source: str, destination: Path) -> None:
    dot_executable = shutil.which("dot")
    if dot_executable is None:
        raise SystemExit(
            "Graphviz 'dot' executable not found. Install graphviz to enable SVG generation."
        )

    process = subprocess.run(
        [dot_executable, "-Tsvg", "-o", str(destination)],
        input=dot_source.encode("utf-8"),
        check=True,
    )

    if process.returncode != 0:  # pragma: no cover - subprocess.run with check=True already raises
        raise SystemExit("Failed to render SVG using graphviz.")


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    project_root = determine_project_root()

    # Ensure the analysed packages can be imported even when the script is
    # executed from another working directory (e.g., via Taskfile).
    with suppress(ValueError):
        sys.path.remove(str(project_root))
    sys.path.insert(0, str(project_root))

    output_dir = args.output_dir or project_root / "dashboard" / "dependency-graph"
    output_dir.mkdir(parents=True, exist_ok=True)

    graph = build_graph(args.packages, include_external=args.include_external)
    modules = sorted(graph.modules)
    edges = collect_edges(graph)

    json_path = output_dir / args.json_name
    svg_path = output_dir / args.svg_name

    serialise_json(args.packages, modules, edges, json_path)

    dot_source = build_dot(modules, edges)
    if args.dot_name:
        (output_dir / args.dot_name).write_text(dot_source)

    render_svg(dot_source, svg_path)

    rel_output = output_dir.relative_to(project_root)
    print(f"Wrote JSON dependency data to {rel_output / args.json_name}")
    print(f"Wrote SVG dependency graph to {rel_output / args.svg_name}")


if __name__ == "__main__":
    main()
