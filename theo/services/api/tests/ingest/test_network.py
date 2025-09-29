"""Tests for ingestion network helpers."""

from __future__ import annotations

import pytest

from theo.services.api.app.ingest.pipeline.exceptions import UnsupportedSourceError
from theo.services.api.app.ingest.pipeline.network import ensure_url_allowed


class _Settings:
    def __init__(self, **overrides):
        self.user_agent = "pytest"
        self.ingest_url_blocked_schemes = []
        self.ingest_url_allowed_schemes: list[str] = []
        self.ingest_url_blocked_hosts: list[str] = []
        self.ingest_url_allowed_hosts: list[str] = []
        self.ingest_url_block_private_networks = True
        self.ingest_url_blocked_ip_networks: list[str] = []
        for key, value in overrides.items():
            setattr(self, key, value)


def test_allow_https_public_host() -> None:
    settings = _Settings()
    ensure_url_allowed(settings, "https://example.com/resource")


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/resource",
        "https://user:pass@example.com/",
    ],
)
def test_reject_disallowed_urls(url: str) -> None:
    settings = _Settings(ingest_url_blocked_schemes=["ftp"])
    with pytest.raises(UnsupportedSourceError):
        ensure_url_allowed(settings, url)


def test_reject_private_network_ip() -> None:
    settings = _Settings()
    with pytest.raises(UnsupportedSourceError):
        ensure_url_allowed(settings, "https://127.0.0.1/resource")


def test_allow_listed_private_host() -> None:
    settings = _Settings(ingest_url_allowed_hosts=["127.0.0.1"])
    ensure_url_allowed(settings, "https://127.0.0.1/internal")
