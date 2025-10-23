from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import ip_address, ip_network

import pytest

from theo.services.api.app.ingest import network as ingest_network
from theo.services.api.app.ingest.exceptions import UnsupportedSourceError
from theo.services.api.app.ingest.pipeline import ensure_url_allowed


@dataclass
class FakeSettings:
    ingest_url_allowed_hosts: list[str] = field(default_factory=list)
    ingest_url_blocked_hosts: list[str] = field(default_factory=list)
    ingest_url_blocked_ip_networks: list[str] = field(default_factory=list)
    ingest_url_allowed_schemes: list[str] = field(default_factory=lambda: ["http", "https"])
    ingest_url_blocked_schemes: list[str] = field(default_factory=list)
    ingest_url_block_private_networks: bool = True


def test_allowlisted_host_with_dns_failure_is_permitted(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = FakeSettings(ingest_url_allowed_hosts=["allowed.test"])
    url = "https://allowed.test/resource"

    original_resolver = ingest_network.resolve_host_addresses

    def failing_ensure(settings_arg, url_arg):
        assert settings_arg is settings
        assert url_arg == url
        raise UnsupportedSourceError("resolver rejected")

    def failing_resolve(host: str):
        assert host == "allowed.test"
        raise UnsupportedSourceError("dns failed")

    monkeypatch.setattr(ingest_network, "ensure_url_allowed", failing_ensure)
    monkeypatch.setattr(
        "theo.services.api.app.ingest.pipeline._resolve_host_addresses",
        failing_resolve,
    )

    # Should not raise due to explicit allow-list override despite DNS failure.
    ensure_url_allowed(settings, url)
    assert ingest_network.resolve_host_addresses is original_resolver


def test_allowlisted_host_blocked_by_network_ranges(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = FakeSettings(
        ingest_url_allowed_hosts=["blocked.test"],
        ingest_url_blocked_ip_networks=["8.8.8.0/24"],
    )
    url = "https://blocked.test/path"

    original_resolver = ingest_network.resolve_host_addresses

    def failing_ensure(*args, **kwargs):
        raise UnsupportedSourceError("resolver rejected")

    monkeypatch.setattr(ingest_network, "ensure_url_allowed", failing_ensure)
    monkeypatch.setattr(
        "theo.services.api.app.ingest.pipeline._resolve_host_addresses",
        lambda host: (ip_address("8.8.8.8"),),
    )
    monkeypatch.setattr(
        ingest_network,
        "cached_blocked_networks",
        lambda networks: (ip_network("8.8.8.0/24"),),
    )

    with pytest.raises(UnsupportedSourceError):
        ensure_url_allowed(settings, url)

    assert ingest_network.resolve_host_addresses is original_resolver


def test_ensure_url_allowed_reraises_for_non_allowlisted_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = FakeSettings(ingest_url_allowed_hosts=["allowed.test"])
    url = "https://blocked.test/path"

    original_resolver = ingest_network.resolve_host_addresses

    def failing_ensure(settings_arg, url_arg):
        assert settings_arg is settings
        assert url_arg == url
        raise UnsupportedSourceError("blocked")

    monkeypatch.setattr(ingest_network, "ensure_url_allowed", failing_ensure)

    with pytest.raises(UnsupportedSourceError) as excinfo:
        ensure_url_allowed(settings, url)

    assert "blocked" in str(excinfo.value)
    assert ingest_network.resolve_host_addresses is original_resolver
