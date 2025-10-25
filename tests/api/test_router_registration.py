"""Ensure API routers are mounted with the expected configuration."""
from __future__ import annotations

from fastapi import FastAPI

from theo.services.api.app.bootstrap import ROUTER_REGISTRATIONS, create_app
from theo.services.api.app.security import require_principal


def test_router_registration_metadata(monkeypatch):
    recorded_calls: list[tuple[object, dict[str, object]]] = []
    original_include_router = FastAPI.include_router

    def capture_include_router(self, router, *args, **kwargs):  # type: ignore[override]
        recorded_calls.append((router, dict(kwargs)))
        return original_include_router(self, router, *args, **kwargs)

    monkeypatch.setenv("THEO_API_KEYS", '["router-test-key"]')
    monkeypatch.setenv("SETTINGS_SECRET_KEY", "router-test-secret")
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.lifecycle.Base.metadata.create_all",
        lambda *_, **__: None,
    )
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.lifecycle.run_sql_migrations",
        lambda *_, **__: None,
    )
    monkeypatch.setattr(
        "theo.services.api.app.bootstrap.lifecycle.seed_reference_data",
        lambda *_, **__: None,
    )
    monkeypatch.setattr(FastAPI, "include_router", capture_include_router)

    app = create_app()
    assert app  # sanity guard against regressions

    assert len(recorded_calls) == len(ROUTER_REGISTRATIONS)

    remaining = {id(registration.router): registration for registration in ROUTER_REGISTRATIONS}
    for router, kwargs in recorded_calls:
        router_id = id(router)
        assert router_id in remaining
        registration = remaining.pop(router_id)

        if registration.prefix is None:
            assert "prefix" not in kwargs
        else:
            assert kwargs.get("prefix") == registration.prefix

        assert kwargs.get("tags") == list(registration.tags)

        dependencies = kwargs.get("dependencies")
        if registration.requires_security:
            assert dependencies, "secured routers must include authentication dependency"
            assert len(dependencies) == 1
            dependency = dependencies[0]
            assert getattr(dependency, "dependency", None) is require_principal
        else:
            assert not dependencies

    assert not remaining
