"""Architecture enforcement for the hexagonal module plan."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

import pytest

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

    class _Collector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.skip_stack: list[bool] = []

        def visit_If(self, node: ast.If) -> None:  # noqa: N802 - AST callback
            is_type_checking = False
            test = node.test
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                is_type_checking = True
            elif isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
                is_type_checking = True

            self.skip_stack.append(is_type_checking)
            if not is_type_checking:
                for child in node.body:
                    self.visit(child)
            # Always visit orelse as the guard does not apply there.
            for child in node.orelse:
                self.visit(child)
            self.skip_stack.pop()

        def visit_Import(self, node: ast.Import) -> None:  # noqa: N802 - AST callback
            if any(self.skip_stack):
                return
            for alias in node.names:
                if alias.name:
                    imports.add(alias.name)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
            if any(self.skip_stack):
                return
            if node.module:
                imports.add(node.module)

        def generic_visit(self, node: ast.AST) -> None:  # noqa: N802
            # Propagate skip flag through nested scopes.
            if any(self.skip_stack):
                for child in ast.iter_child_nodes(node):
                    self.visit(child)
            else:
                super().generic_visit(node)

    _Collector().visit(tree)
    return imports


def test_domain_isolation() -> None:
    forbidden_prefixes = (
        "theo.adapters",
        "theo.infrastructure",
        "fastapi",
        "sqlalchemy",
        "celery",
    )
    for path in _iter_python_files("theo.domain"):
        for module in _gather_imports(path):
            if not module.startswith("theo"):
                continue
            assert not module.startswith(forbidden_prefixes), (
                f"Domain module {path} imports forbidden dependency '{module}'"
            )


def test_application_depends_only_on_domain_and_platform() -> None:
    allowed_prefixes = (
        "theo.application",
        "theo.domain",
        "theo.platform",
        "theo.adapters",
    )
    forbidden_prefixes = ("theo.infrastructure",)
    for path in _iter_python_files("theo.application"):
        if "facades" in path.parts:
            continue
        if "tests" in path.parts:
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


def test_application_does_not_import_service_database() -> None:
    forbidden_prefix = "theo.infrastructure.api.app.db"
    for path in _iter_python_files("theo.application"):
        for module in _gather_imports(path):
            if not module.startswith("theo"):
                continue
            assert not module.startswith(forbidden_prefix), (
                f"Application module {path} imports forbidden database dependency '{module}'"
            )


def test_application_does_not_import_service_runtimes_or_fastapi() -> None:
    forbidden_service_prefix = "theo.infrastructure.api.app"
    forbidden_adapters = (
        "theo.infrastructure.api.app.adapters.telemetry",
        "theo.infrastructure.api.app.adapters.resilience",
        "theo.infrastructure.api.app.adapters.security",
    )
    for path in _iter_python_files("theo.application"):
        if "tests" in path.parts:
            continue
        for module in _gather_imports(path):
            for adapter in forbidden_adapters:
                if module == adapter or module.startswith(f"{adapter}."):
                    pytest.fail(
                        f"Application module {path} imports forbidden adapter '{module}'"
                    )
            if module.startswith(forbidden_service_prefix):
                pytest.fail(
                    f"Application module {path} must not import service-layer runtime module '{module}'"
                )
            if module == "fastapi" or module.startswith("fastapi."):
                pytest.fail(
                    f"Application module {path} imports FastAPI dependency '{module}'"
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
    forbidden_prefix = "theo.infrastructure.api.app.core"
    for path in _iter_python_files("theo/infrastructure/api/app/routes"):
        imports = _gather_imports(path)
        assert forbidden_prefix not in imports, (
            f"Route module {path} must import facades instead of legacy core modules"
        )


def test_workers_use_platform_bootstrap() -> None:
    workers_path = REPO_ROOT / "theo/infrastructure/api/app/workers"
    for path in workers_path.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        imports = _gather_imports(path)
        assert "theo.application.services.bootstrap" in imports, (
            f"Worker module {path} must resolve adapters via theo.application.services.bootstrap"
        )


def test_cli_commands_use_platform_bootstrap() -> None:
    cli_root = REPO_ROOT / "theo/application/services/cli"
    for path in cli_root.rglob("*.py"):
        if "/tests/" in path.as_posix():
            continue
        imports = _gather_imports(path)
        assert "theo.application.services.bootstrap" in imports, (
            f"CLI module {path} must resolve adapters via theo.application.services.bootstrap"
        )


def test_async_workers_do_not_depend_on_domain_layer() -> None:
    workers_path = REPO_ROOT / "theo/infrastructure/api/app/workers"
    for path in workers_path.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        for module in _gather_imports(path):
            assert not module.startswith("theo.domain"), (
                f"Async worker module {path} must not import domain layer module '{module}'"
            )


def test_api_adapters_live_under_infra_namespace() -> None:
    legacy_services_path = REPO_ROOT / "theo/infrastructure/api/app/services"
    assert not legacy_services_path.exists(), (
        "Legacy API services package reintroduced; adapters must live in 'infra'."
    )

    infra_path = REPO_ROOT / "theo/infrastructure/api/app/infra"
    assert infra_path.exists(), "API infrastructure adapters must live under 'infra'."
    adapter_modules = list(infra_path.rglob("*.py"))
    assert adapter_modules, "Infrastructure namespace should contain adapter modules."
