from types import SimpleNamespace

import pytest

from theo.services.api.app.ingest.exceptions import UnsupportedSourceError
from theo.services.api.app.ingest.network import ensure_url_allowed


def _make_settings(**overrides):
    base = {
        "ingest_url_blocked_ip_networks": [],
        "ingest_url_block_private_networks": False,
        "ingest_url_blocked_schemes": [],
        "ingest_url_allowed_schemes": [],
        "ingest_url_allowed_hosts": [],
        "ingest_url_blocked_hosts": [],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_allow_well_formed_https_url():
    settings = _make_settings()
    ensure_url_allowed(settings, "https://127.0.0.1/resource")


def test_reject_blocked_scheme():
    settings = _make_settings(ingest_url_blocked_schemes=["javascript"])
    with pytest.raises(UnsupportedSourceError):
        ensure_url_allowed(settings, "javascript:alert(1)")


def test_reject_blocked_host():
    settings = _make_settings(ingest_url_blocked_hosts=["192.0.2.1"])
    with pytest.raises(UnsupportedSourceError):
        ensure_url_allowed(settings, "https://192.0.2.1/path")

