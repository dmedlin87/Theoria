"""Ensure pinned constraint files cover declared optional dependencies."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from packaging.requirements import Requirement


REPO_ROOT = Path(__file__).resolve().parents[1]
CONSTRAINT_FILES = {
    "prod": REPO_ROOT / "constraints" / "prod.txt",
    "dev": REPO_ROOT / "constraints" / "dev.txt",
}
EXTRA_TO_CONSTRAINT = {
    "base": "prod",
    "api": "prod",
    "ml": "prod",
    "dev": "dev",
}

_REQUIREMENT_RE = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[.*\])?==")


def _parse_constraint_packages(path: Path) -> set[str]:
    packages: set[str] = set()
    for line in path.read_text().splitlines():
        match = _REQUIREMENT_RE.match(line)
        if match:
            packages.add(match.group(1).lower())
    return packages


def test_optional_dependencies_are_constrained() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    optional_deps = pyproject["project"]["optional-dependencies"]

    cache: dict[str, set[str]] = {}
    missing: dict[str, dict[str, list[str]]] = {}

    for extra_name, dependencies in optional_deps.items():
        target_key = EXTRA_TO_CONSTRAINT.get(extra_name)
        assert (
            target_key is not None
        ), f"No constraint file mapping defined for extra '{extra_name}'"

        constraint_path = CONSTRAINT_FILES[target_key]
        packages = cache.setdefault(target_key, _parse_constraint_packages(constraint_path))

        extra_missing: list[str] = []
        for spec in dependencies:
            requirement = Requirement(spec)
            if requirement.name.lower() not in packages:
                extra_missing.append(requirement.name)

        if extra_missing:
            missing.setdefault(str(constraint_path), {})[extra_name] = extra_missing

    assert not missing, (
        "Missing pinned constraints for extras: "
        + "; ".join(
            f"{constraint} -> "
            + ", ".join(
                f"{extra}: {', '.join(sorted(packages))}" for extra, packages in extras.items()
            )
            for constraint, extras in missing.items()
        )
    )
