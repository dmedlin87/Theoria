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


def test_resolve_invokes_factory_each_time():
    registry = AdapterRegistry()
    calls: list[int] = []

    def factory() -> object:
        calls.append(len(calls))
        return object()

    registry.register("counter", factory)

    first = registry.resolve("counter")
    second = registry.resolve("counter")

    assert first is not second
    assert calls == [0, 1]
