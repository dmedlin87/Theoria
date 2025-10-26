"""Architecture tests for DTO and repository boundaries.

Ensures that service layer uses DTOs instead of ORM models,
and that repositories properly abstract persistence layer.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]


def _iter_python_files(package: str) -> Iterable[Path]:
    """Iterate over Python files in a package."""
    root = REPO_ROOT / package.replace(".", "/")
    for path in root.rglob("*.py"):
        yield path


def _gather_imports(path: Path) -> set[str]:
    """Extract all import statements from a Python file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def test_repositories_use_dtos_not_orm():
    """Repository implementations should work with DTOs, not expose ORM models."""
    for path in _iter_python_files("theo/adapters/persistence"):
        if not path.name.endswith("_repository.py"):
            continue

        # Check that repository files import DTOs
        imports = _gather_imports(path)

        # Should import from application layer
        has_dto_import = any(
            "theo.application.dtos" in imp for imp in imports
        )

        if "repository" in path.stem:
            assert has_dto_import, (
                f"Repository {path} should import DTOs from application.dtos"
            )


def test_services_no_direct_orm_imports():
    """Service layer should not import ORM models directly."""
    forbidden_imports = [
        "theo.adapters.persistence.models",
    ]

    for path in _iter_python_files("theo/services/api/app"):
        # Skip database and adapter-specific modules (handle any path separators)
        if "db" in path.parts or "compat" in path.parts:
            continue

        imports = _gather_imports(path)

        for forbidden in forbidden_imports:
            # Check if any import starts with forbidden prefix
            violations = [imp for imp in imports if imp.startswith(forbidden)]

            assert not violations, (
                f"Service module {path} imports ORM models directly: {violations}. "
                f"Use DTOs from theo.application.dtos instead."
            )


def test_dtos_are_immutable_dataclasses():
    """DTOs should be frozen dataclasses for immutability."""
    dto_file = REPO_ROOT / "theo" / "application" / "dtos" / "discovery.py"

    if not dto_file.exists():
        return  # Skip if DTOs not yet created

    content = dto_file.read_text(encoding="utf-8")
    tree = ast.parse(content)

    # Find all classes
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name.endswith("DTO"):
                # Check for @dataclass decorator with frozen=True
                has_frozen = False
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if hasattr(decorator.func, "id") and decorator.func.id == "dataclass":
                            # Check for frozen keyword arg
                            for keyword in decorator.keywords:
                                if keyword.arg == "frozen" and isinstance(keyword.value, ast.Constant):
                                    has_frozen = keyword.value.value

                assert has_frozen, (
                    f"DTO {node.name} in {dto_file} should be a frozen dataclass: "
                    f"@dataclass(frozen=True)"
                )


def test_mappers_bidirectional():
    """Mapper module should provide bidirectional conversion functions."""
    mappers_file = REPO_ROOT / "theo" / "adapters" / "persistence" / "mappers.py"

    if not mappers_file.exists():
        return  # Skip if mappers not yet created

    content = mappers_file.read_text(encoding="utf-8")

    # Should have both directions of mapping
    assert "to_dto" in content, "Mappers should include model_to_dto functions"
    assert "dto_to_" in content or "to_model" in content, (
        "Mappers should include dto_to_model functions"
    )


def test_repository_interfaces_in_application_layer():
    """Repository interfaces should be defined in application layer, not adapters."""
    app_repo_path = REPO_ROOT / "theo" / "application" / "repositories"

    if not app_repo_path.exists():
        return  # Skip if not yet created

    # Check that repository interfaces exist in application layer
    interface_files = list(app_repo_path.glob("*_repository.py"))

    assert len(interface_files) > 0, (
        "Repository interfaces should be defined in theo/application/repositories/"
    )

    # Verify they contain abstract methods
    for repo_file in interface_files:
        content = repo_file.read_text(encoding="utf-8")

        assert "ABC" in content or "abstractmethod" in content, (
            f"Repository interface {repo_file.name} should use ABC and @abstractmethod"
        )


def test_no_sqlalchemy_in_application_layer():
    """Application layer should not depend on SQLAlchemy."""
    forbidden_imports = [
        "sqlalchemy",
    ]

    for path in _iter_python_files("theo/application"):
        # Skip facades which are allowed to interface with adapters
        if "facades" in str(path):
            continue

        imports = _gather_imports(path)

        for forbidden in forbidden_imports:
            violations = [imp for imp in imports if imp.startswith(forbidden)]

            assert not violations, (
                f"Application module {path} imports SQLAlchemy: {violations}. "
                f"Application layer should be ORM-agnostic."
            )
