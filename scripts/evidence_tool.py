"""Lightweight tooling for working with local evidence card files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Iterator, Sequence

DEFAULT_SOURCE_DIR = Path("evidence/cards")
DEFAULT_REGISTRY_DIR = Path("evidence/registry")
DEFAULT_JSONL_PATH = DEFAULT_REGISTRY_DIR / "evidence.index.jsonl"


def _resolve_base_path(base_path: str | None) -> Path:
    base = Path(base_path) if base_path else Path.cwd()
    return base.expanduser().resolve()


def _iter_input_files(paths: Sequence[str] | None, *, base_path: Path) -> Iterator[Path]:
    if not paths:
        paths = [str(DEFAULT_SOURCE_DIR)]

    for raw in paths:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = base_path / candidate
        candidate = candidate.expanduser().resolve()
        if candidate.is_dir():
            for child in sorted(candidate.iterdir()):
                if child.is_file() and child.suffix.lower() in {".json", ".jsonl"}:
                    yield child
        elif candidate.is_file():
            yield candidate
        else:
            raise FileNotFoundError(f"Evidence resource not found: {candidate}")


def _load_records(path: Path) -> list[dict[str, object]]:
    if path.suffix.lower() == ".jsonl":
        records: list[dict[str, object]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError(f"Expected object at {path}:{line_no}")
                records.append(record)
        return records

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        records = []
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                raise ValueError(f"Expected object at {path} index {index}")
            records.append(item)
        return records
    raise ValueError(f"Unsupported JSON payload in {path}")


def _collect_records(paths: Sequence[str] | None, *, base_path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for file_path in _iter_input_files(paths, base_path=base_path):
        records.extend(_load_records(file_path))
    return _deduplicate_records(records)


def _deduplicate_records(records: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    deduped: dict[str, dict[str, object]] = {}
    fallback = 0
    for record in records:
        key: str | None = None
        value = record
        if isinstance(record, dict):
            raw_sid = record.get("sid")
            if isinstance(raw_sid, str) and raw_sid:
                key = raw_sid
        if key is None:
            key = f"record-{fallback}"
            fallback += 1
        if key not in deduped:
            deduped[key] = value
    return list(deduped.values())


def _write_jsonl(path: Path, records: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _format_summary(records: Iterable[dict[str, object]]) -> dict[str, object]:
    summary: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        tags = record.get("tags")
        if isinstance(tags, (list, tuple)):
            filtered_tags = sorted({str(tag) for tag in tags if isinstance(tag, str) and tag})
        else:
            filtered_tags = []
        summary.append(
            {
                "sid": record.get("sid"),
                "title": record.get("title"),
                "summary": record.get("summary"),
                "tags": filtered_tags,
            }
        )
    return {"records": summary, "total": len(summary)}


def _handle_validate(args: argparse.Namespace) -> None:
    base_path = _resolve_base_path(args.base_path)
    records = _collect_records(args.paths, base_path=base_path)
    print(json.dumps(records, indent=2, ensure_ascii=False))


def _handle_index(args: argparse.Namespace) -> None:
    base_path = _resolve_base_path(args.base_path)
    records = _collect_records(args.paths, base_path=base_path)
    target = Path(args.jsonl or DEFAULT_JSONL_PATH)
    if not target.is_absolute():
        target = base_path / target
    _write_jsonl(target, records)
    print(f"Indexed {len(records)} records into {target}")


def _handle_promote(args: argparse.Namespace) -> None:
    base_path = _resolve_base_path(args.base_path)
    records = _collect_records(args.paths, base_path=base_path)
    destination = Path(args.output)
    if not destination.is_absolute():
        destination = base_path / destination
    if destination.is_dir() or destination.suffix == "":
        destination.mkdir(parents=True, exist_ok=True)
        destination = destination / "evidence.promoted.json"
    _write_json(destination, records)
    print(f"Promoted {len(records)} records to {destination}")


def _handle_dossier(args: argparse.Namespace) -> None:
    base_path = _resolve_base_path(args.base_path)
    records = _collect_records(args.paths, base_path=base_path)
    if args.tags:
        tag_filter = {tag.strip().lower() for tag in args.tags if tag.strip()}
        if tag_filter:
            filtered: list[dict[str, object]] = []
            for record in records:
                if not isinstance(record, dict):
                    continue
                tags = record.get("tags")
                if not isinstance(tags, (list, tuple)):
                    continue
                normalised = {str(tag).lower() for tag in tags if isinstance(tag, str)}
                if normalised & tag_filter:
                    filtered.append(record)
            records = filtered
    payload = _format_summary(records)
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = base_path / out_path
        if out_path.is_dir() or out_path.suffix == "":
            out_path.mkdir(parents=True, exist_ok=True)
            out_path = out_path / "dossier.json"
        _write_json(out_path, payload)
        print(f"Wrote dossier summary to {out_path}")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simple helpers for evidence records")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate evidence payloads")
    validate.add_argument("paths", nargs="*", help="Files or directories to validate")
    validate.add_argument("--base-path", dest="base_path", help="Resolve inputs relative to this path")
    validate.set_defaults(func=_handle_validate)

    index = subparsers.add_parser("index", help="Build a JSONL index from evidence payloads")
    index.add_argument("paths", nargs="*", help="Files or directories to index")
    index.add_argument("--jsonl", help="Destination JSONL path")
    index.add_argument("--base-path", dest="base_path", help="Resolve inputs relative to this path")
    index.set_defaults(func=_handle_index)

    promote = subparsers.add_parser("promote", help="Copy validated payloads to a target directory")
    promote.add_argument("paths", nargs="*", help="Files or directories to promote")
    promote.add_argument("--output", required=True, help="Destination file or directory")
    promote.add_argument("--base-path", dest="base_path", help="Resolve inputs relative to this path")
    promote.set_defaults(func=_handle_promote)

    dossier = subparsers.add_parser("dossier", help="Generate a lightweight dossier summary")
    dossier.add_argument("paths", nargs="*", help="Files or directories to summarise")
    dossier.add_argument("--out", dest="out", help="Write dossier JSON to this path")
    dossier.add_argument("--tags", nargs="*", help="Optional tag filters")
    dossier.add_argument("--base-path", dest="base_path", help="Resolve inputs relative to this path")
    dossier.set_defaults(func=_handle_dossier)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except FileNotFoundError as exc:  # pragma: no cover - user error path
        parser.error(str(exc))
    except ValueError as exc:  # pragma: no cover - validation errors
        parser.error(str(exc))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
