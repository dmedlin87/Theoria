#!/usr/bin/env python3
"""Refresh extras constraint lockfiles.

Usage:
    python scripts/update_constraints.py          # rewrite constraint files
    python scripts/update_constraints.py --check  # verify files are up to date
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS_DIR = REPO_ROOT / "constraints"

EXTRAS = {
    "base": CONSTRAINTS_DIR / "base-constraints.txt",
    "api": CONSTRAINTS_DIR / "api-constraints.txt",
    "ml": CONSTRAINTS_DIR / "ml-constraints.txt",
    "dev": CONSTRAINTS_DIR / "dev-constraints.txt",
}

CPU_TORCH_INDEX = "https://download.pytorch.org/whl/cpu"
DEFAULT_PYPI_INDEX = "https://pypi.org/simple"
PIP_ARGS = {
    "ml": f"--index-url {CPU_TORCH_INDEX} --extra-index-url {DEFAULT_PYPI_INDEX}",
}


def run_pip_compile(extra: str, destination: Path) -> Path:
    """Run pip-compile for a specific extra and return the generated file path."""
    try:
        relative_output = destination.relative_to(REPO_ROOT)
    except ValueError:
        relative_output = destination

    cmd = [
        sys.executable,
        "-m",
        "piptools",
        "compile",
        "--resolver=backtracking",
        f"--extra={extra}",
        "--allow-unsafe",
        "--generate-hashes",
        "--quiet",
        "--output-file",
        str(relative_output),
        "pyproject.toml",
    ]
    pip_args = PIP_ARGS.get(extra)
    if pip_args:
        cmd.extend(["--pip-args", pip_args])
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)
    return destination


def check_constraints() -> bool:
    ok = True
    for extra, destination in EXTRAS.items():
        original_bytes = destination.read_bytes() if destination.exists() else None
        try:
            run_pip_compile(extra, destination)
        except subprocess.CalledProcessError:
            if original_bytes is None:
                destination.unlink(missing_ok=True)
            else:
                destination.write_bytes(original_bytes)
            raise

        updated_bytes = destination.read_bytes()
        if original_bytes is None:
            print(
                f"Missing constraint file for '{extra}' (expected {destination}).",
                file=sys.stderr,
            )
            ok = False
        elif original_bytes != updated_bytes:
            print(
                f"Constraint file '{destination.relative_to(REPO_ROOT)}' is out of date; "
                f"run update_constraints.py.",
                file=sys.stderr,
            )
            ok = False

        if original_bytes is None:
            destination.unlink(missing_ok=True)
        else:
            destination.write_bytes(original_bytes)
    return ok


def update_constraints() -> None:
    CONSTRAINTS_DIR.mkdir(exist_ok=True)
    for extra, destination in EXTRAS.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        print(f"Updating constraints for extra '{extra}' -> {destination.relative_to(REPO_ROOT)}")
        run_pip_compile(extra, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh dependency constraint lockfiles.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that the constraint files match the resolved extras without rewriting them.",
    )
    args = parser.parse_args(argv)

    if args.check:
        return 0 if check_constraints() else 1

    update_constraints()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
