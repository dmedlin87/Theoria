import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.services.api.app.core.settings import Settings


def test_ingest_string_collections_strip_and_filter_blank_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure environment variables do not interfere with the Settings instantiation
    monkeypatch.delenv("SETTINGS_SECRET_KEY", raising=False)

    settings = Settings(
        ingest_url_allowed_hosts=[" example.com ", "   ", "\nexample.org\n"],
        ingest_url_blocked_hosts=["  bad.com", ""],
        ingest_url_blocked_ip_networks=[" 10.0.0.0/8 ", "   "],
    )

    assert settings.ingest_url_allowed_hosts == ["example.com", "example.org"]
    assert settings.ingest_url_blocked_hosts == ["bad.com"]
    assert settings.ingest_url_blocked_ip_networks == ["10.0.0.0/8"]
