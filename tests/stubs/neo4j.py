"""Neo4j shim used by bootstrap tests."""

from __future__ import annotations

from types import ModuleType, SimpleNamespace

__all__ = ["build_neo4j_stub"]


def build_neo4j_stub() -> dict[str, ModuleType]:
    module = ModuleType("neo4j")
    module.GraphDatabase = SimpleNamespace(driver=lambda *_args, **_kwargs: SimpleNamespace())
    return {"neo4j": module}
