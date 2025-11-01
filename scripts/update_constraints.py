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

TARGETS = {
    "prod": {
        "extras": ("base", "api", "ml"),
        "destination": CONSTRAINTS_DIR / "prod.txt",
    },
    "dev": {
        "extras": ("base", "api", "ml", "dev"),
        "destination": CONSTRAINTS_DIR / "dev.txt",
    },
}




def run_uv_compile(extras: tuple[str, ...], destination: Path) -> Path:
    """Run uv pip compile for a combination of extras and return the generated file path."""
    try:
        relative_output = destination.relative_to(REPO_ROOT)
    except ValueError:
        relative_output = destination

    cmd = [
        "python",
        "-m",
        "uv",
        "pip",
        "compile",
        "--quiet",
    ]
    for extra in extras:
        cmd.append(f"--extra={extra}")

    cmd.extend([
        "--output-file",
        relative_output.as_posix(),
        "pyproject.toml",
    ])

    if "ml" in extras:
        # Add index strategy to allow searching across multiple indexes
        cmd.extend(["--index-strategy", "unsafe-best-match"])
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)
    return destination

def check_constraints() -> bool:
    ok = True
    for name, config in TARGETS.items():
        destination = config["destination"]
        extras = config["extras"]
        original_bytes = destination.read_bytes() if destination.exists() else None

        try:
            run_uv_compile(extras, destination)
        except subprocess.CalledProcessError:
            if original_bytes is None:
                destination.unlink(missing_ok=True)
            else:
                destination.write_bytes(original_bytes)
            raise

        updated_bytes = destination.read_bytes()
        if original_bytes is None:
            print(
                f"Missing constraint file for target '{name}' (expected {destination}).",
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
    for name, config in TARGETS.items():
        destination = config["destination"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        print(
            "Updating constraints for target "
            f"'{name}' -> {destination.relative_to(REPO_ROOT)} (extras: {', '.join(config['extras'])})"
        )
        run_uv_compile(config["extras"], destination)


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
