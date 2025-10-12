"""Architecture enforcement for the hexagonal module plan."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]


def _iter_python_files(package: str) -> Iterable[Path]:
    root = REPO_ROOT / package.replace(".", "/")
    for path in root.rglob("*.py"):
        if path.name == "__init__.py":
            yield path
        else:
            yield path


def _gather_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
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


def test_domain_isolation() -> None:
    forbidden_prefixes = ("theo.adapters", "theo.services", "fastapi", "sqlalchemy", "celery")
    for path in _iter_python_files("theo.domain"):
        for module in _gather_imports(path):
            if not module.startswith("theo"):
                continue
            assert not module.startswith(forbidden_prefixes), (
                f"Domain module {path} imports forbidden dependency '{module}'"
            )


def test_application_depends_only_on_domain_and_platform() -> None:
    allowed_prefixes = ("theo.application", "theo.domain", "theo.platform", "theo.adapters")
    forbidden_prefixes = ("theo.services",)
    for path in _iter_python_files("theo.application"):
        if "facades" in path.parts:
            continue
        for module in _gather_imports(path):
            if not module.startswith("theo"):
                continue
            assert module.startswith(allowed_prefixes), (
                f"Application module {path} imports '{module}', which violates layering"
            )
            assert not module.startswith(forbidden_prefixes), (
                f"Application module {path} must not depend on {module}"
            )


def test_adapters_do_not_cross_import() -> None:
    forbidden_edges = {
        "theo.adapters.interfaces": ("theo.adapters.persistence", "theo.adapters.search", "theo.adapters.ai"),
    }
    for path in _iter_python_files("theo.adapters"):
        imports = _gather_imports(path)
        for source_prefix, disallowed_targets in forbidden_edges.items():
            if not path.as_posix().startswith((REPO_ROOT / source_prefix.replace(".", "/")).as_posix()):
                continue
            for module in imports:
                for target in disallowed_targets:
                    assert not module.startswith(target), (
                        f"Interface adapter {path} must not import '{module}'"
                    )


def test_routes_depend_on_application_facades() -> None:
    forbidden_prefix = "theo.services.api.app.core"
    for path in _iter_python_files("theo/services/api/app/routes"):
        imports = _gather_imports(path)
        assert forbidden_prefix not in imports, (
            f"Route module {path} must import facades instead of legacy core modules"
        )


def test_workers_use_platform_bootstrap() -> None:
    workers_path = REPO_ROOT / "theo/services/api/app/workers"
    for path in workers_path.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        imports = _gather_imports(path)
        assert "theo.services.bootstrap" in imports, (
            f"Worker module {path} must resolve adapters via theo.services.bootstrap"
        )


def test_cli_commands_use_platform_bootstrap() -> None:
    cli_root = REPO_ROOT / "theo/services/cli"
    for path in cli_root.rglob("*.py"):
        if "/tests/" in path.as_posix():
            continue
        imports = _gather_imports(path)
        assert "theo.services.bootstrap" in imports, (
            f"CLI module {path} must resolve adapters via theo.services.bootstrap"
        )


def test_async_workers_do_not_depend_on_domain_layer() -> None:
    workers_path = REPO_ROOT / "theo/services/api/app/workers"
    for path in workers_path.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        for module in _gather_imports(path):
            assert not module.startswith("theo.domain"), (
                f"Async worker module {path} must not import domain layer module '{module}'"
            )
