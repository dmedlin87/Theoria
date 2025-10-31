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

CPU_TORCH_INDEX = "https://download.pytorch.org/whl/cpu"
DEFAULT_PYPI_INDEX = "https://pypi.org/simple"
TORCH_PIP_ARGS = f"--index-url {CPU_TORCH_INDEX} --extra-index-url {DEFAULT_PYPI_INDEX}"


def ensure_pip_tools_compatibility() -> None:
    """Ensure pip and pip-tools versions are compatible."""
    try:
        # Check current pip version
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        pip_version = result.stdout.strip()
        print(f"Using {pip_version}")
        
        # Check pip-tools version
        result = subprocess.run(
            [sys.executable, "-m", "piptools", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        piptools_version = result.stdout.strip()
        print(f"Using pip-tools {piptools_version}")
        
    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not verify pip-tools compatibility: {e}", file=sys.stderr)
        print("Attempting to install compatible versions...", file=sys.stderr)
        
        try:
            # Install compatible versions
            subprocess.run([
                sys.executable, "-m", "pip", "install", "--upgrade",
                "pip<24.1", "pip-tools>=7.4.1,<7.5"
            ], check=True)
            print("Successfully installed compatible pip and pip-tools versions")
        except subprocess.CalledProcessError as install_error:
            print(f"Failed to install compatible versions: {install_error}", file=sys.stderr)
            raise


def run_pip_compile(extras: tuple[str, ...], destination: Path) -> Path:
    """Run pip-compile for a combination of extras and return the generated file path."""
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
        "--allow-unsafe",
        "--generate-hashes",
        "--quiet",
    ]
    for extra in extras:
        cmd.append(f"--extra={extra}")
    cmd.extend([
        "--output-file",
        str(relative_output),
        "pyproject.toml",
    ])
    if "ml" in extras:
        cmd.extend(["--pip-args", TORCH_PIP_ARGS])
    
    try:
        subprocess.run(cmd, check=True, cwd=REPO_ROOT)
    except subprocess.CalledProcessError as e:
        print(f"\nError running pip-compile for extras {extras}:", file=sys.stderr)
        print(f"Command: {' '.join(cmd)}", file=sys.stderr)
        print(f"Exit code: {e.returncode}", file=sys.stderr)
        
        # Check if this is the known compatibility issue
        if "use_pep517" in str(e) or "AttributeError" in str(e):
            print("\nThis appears to be a pip-tools compatibility issue.", file=sys.stderr)
            print("Try running: pip install --upgrade 'pip<24.1' 'pip-tools>=7.4.1,<7.5'", file=sys.stderr)
        
        raise
    
    return destination


def check_constraints() -> bool:
    # Ensure compatibility before running
    ensure_pip_tools_compatibility()
    
    ok = True
    for name, config in TARGETS.items():
        destination = config["destination"]
        extras = config["extras"]
        original_bytes = destination.read_bytes() if destination.exists() else None
        try:
            run_pip_compile(extras, destination)
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
    # Ensure compatibility before running
    ensure_pip_tools_compatibility()
    
    CONSTRAINTS_DIR.mkdir(exist_ok=True)
    for name, config in TARGETS.items():
        destination = config["destination"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        print(
            "Updating constraints for target "
            f"'{name}' -> {destination.relative_to(REPO_ROOT)} (extras: {', '.join(config['extras'])})"
        )
        run_pip_compile(config["extras"], destination)


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
