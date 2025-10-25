from __future__ import annotations

import ast
from pathlib import Path

import pytest


APPLICATION_ROOT = Path(__file__).resolve().parents[2] / "theo" / "application"


@pytest.mark.parametrize(
    "module_path",
    sorted(APPLICATION_ROOT.rglob("*.py")),
)
def test_application_layer_does_not_depend_on_services(module_path: Path) -> None:
    source = module_path.read_text()
    tree = ast.parse(source, filename=str(module_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("theo.services"):
                    pytest.fail(f"{module_path} imports service layer module {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("theo.services"):
                pytest.fail(f"{module_path} imports service layer module {module}")
