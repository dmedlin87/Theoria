"""Run rag_eval for selected modules and capture before/after metrics."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_OUTPUT_DIR = Path("perf_metrics")
DEFAULT_BASELINE = Path("data/eval/baseline.json")
DEFAULT_DEV_PATH = Path("data/eval/rag_dev.jsonl")
DEFAULT_TRACE_PATH = Path("data/eval/production_traces.jsonl")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run theo.services.cli.rag_eval and record comparison artefacts.",
    )
    parser.add_argument(
        "--modules",
        nargs="*",
        default=None,
        help="Human-readable labels for the modules affected by the change.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where comparison files will be written.",
    )
    parser.add_argument(
        "--dev-path",
        type=Path,
        default=DEFAULT_DEV_PATH,
        help="Path to the curated dev dataset used by rag_eval.",
    )
    parser.add_argument(
        "--trace-path",
        type=Path,
        default=DEFAULT_TRACE_PATH,
        help="Path to the production trace dataset used by rag_eval.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Baseline metrics JSON file consumed by rag_eval.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter used to execute the CLI.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=None,
        help="Optional tolerance override forwarded to rag_eval.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Forward the --update-baseline flag to rag_eval after a successful run.",
    )
    return parser.parse_args()


def _ensure_modules(value: Iterable[str] | None) -> list[str]:
    modules = [item for item in (value or []) if item]
    if not modules:
        return ["global"]
    return sorted(set(modules))


def _invoke_rag_eval(
    module: str,
    output_dir: Path,
    *,
    python_executable: str,
    dev_path: Path,
    trace_path: Path,
    baseline_path: Path,
    tolerance: float | None,
    update_baseline: bool,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"{module}_after.json"

    command = [
        python_executable,
        "-m",
        "theo.services.cli.rag_eval",
        "--dev-path",
        str(dev_path),
        "--trace-path",
        str(trace_path),
        "--baseline",
        str(baseline_path),
        "--output",
        str(output_path),
    ]
    if tolerance is not None:
        command.extend(["--tolerance", str(tolerance)])
    if update_baseline:
        command.append("--update-baseline")

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    
    # Print command for debugging
    print(f"Running command: {' '.join(command)}")
    
    try:
        # Capture output so we can emit it on failure
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        print(result.stdout)
        if result.stderr:
            print(f"rag_eval stderr: {result.stderr}", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        # Emit command, return code, stdout/stderr for CI logs
        print(f"Command failed: {' '.join(e.cmd)}", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        if e.stdout:
            print(f"STDOUT:\n{e.stdout}", file=sys.stderr)
        if e.stderr:
            print(f"STDERR:\n{e.stderr}", file=sys.stderr)
        raise

    marker_path = output_dir / f"{module}_run.txt"
    marker_path.write_text(
        f"rag_eval executed for '{module}' at {timestamp} UTC\n", encoding="utf-8"
    )
    return output_path


def _format_metric(value: object) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value)


def _write_comparison(module: str, output_path: Path, output_dir: Path) -> None:
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    comparison = {
        "module": module,
        "baseline": payload.get("baseline", {}),
        "current": payload.get("overall", {}),
        "tolerance": payload.get("tolerance"),
        "regressions": payload.get("regressions", []),
        "failing_rows": payload.get("failing_rows", []),
        "source_file": output_path.name,
    }
    comparison_path = output_dir / f"{module}_comparison.json"
    comparison_path.write_text(json.dumps(comparison, indent=2, sort_keys=True), encoding="utf-8")

    summary_lines = [
        f"# RAG Evaluation Summary: {module}",
        "",
        "## Baseline (before)",
    ]
    if comparison["baseline"]:
        for metric, value in sorted(comparison["baseline"].items()):
            summary_lines.append(f"- {metric}: {_format_metric(value)}")
    else:
        summary_lines.append("- No baseline metrics available")

    summary_lines.extend(["", "## Current (after)"])
    if comparison["current"]:
        for metric, value in sorted(comparison["current"].items()):
            summary_lines.append(f"- {metric}: {_format_metric(value)}")
    else:
        summary_lines.append("- No current metrics recorded")

    summary_lines.append("")
    if comparison["regressions"]:
        summary_lines.append("## Regressions detected")
        for item in comparison["regressions"]:
            metric = item.get("metric", "?")
            baseline_val = _format_metric(item.get("baseline"))
            current_val = _format_metric(item.get("current"))
            tolerance = _format_metric(item.get("tolerance"))
            summary_lines.append(
                f"- {metric}: {current_val} vs baseline {baseline_val} (tolerance {tolerance})"
            )
    else:
        summary_lines.append("No regressions detected within tolerance.")

    summary_path = output_dir / f"{module}_comparison.md"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")


def main() -> None:
    args = _parse_args()
    modules = _ensure_modules(args.modules)
    
    # Validate required input files exist
    for file_path in [args.dev_path, args.trace_path, args.baseline]:
        if not file_path.exists():
            print(f"Required file not found: {file_path}", file=sys.stderr)
            sys.exit(2)
    
    # Check if modules were detected
    if not modules:
        print("No RAG modules detected (modules list empty). Skipping rag_eval.", file=sys.stderr)
        sys.exit(0)
    
    print(f"Running rag_eval for modules: {', '.join(modules)}")

    for module in modules:
        output_path = _invoke_rag_eval(
            module,
            args.output_dir,
            python_executable=args.python,
            dev_path=args.dev_path,
            trace_path=args.trace_path,
            baseline_path=args.baseline,
            tolerance=args.tolerance,
            update_baseline=args.update_baseline,
        )
        _write_comparison(module, output_path, args.output_dir)


if __name__ == "__main__":
    main()
