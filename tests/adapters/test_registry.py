import pytest

from theo.adapters import AdapterRegistry


def test_register_and_resolve_returns_factory_result():
    registry = AdapterRegistry()
    sentinel = object()

    registry.register("example", lambda: sentinel)

    assert registry.resolve("example") is sentinel


def test_register_rejects_duplicate_ports():
    registry = AdapterRegistry()
    registry.register("duplicate", lambda: object())

    with pytest.raises(ValueError):
        registry.register("duplicate", lambda: object())


def test_resolve_unknown_port_raises_lookup_error():
    registry = AdapterRegistry()

    with pytest.raises(LookupError):
        registry.resolve("missing")
