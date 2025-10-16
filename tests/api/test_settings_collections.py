import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from theo.application.facades.settings import Settings


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


@pytest.mark.parametrize(
    "value, expected",
    [
        ("[\"alpha\", \"beta\", \"\"]", ["alpha", "beta"]),
        ("gamma, delta , , epsilon", ["GAMMA", "DELTA", "EPSILON"]),
        (["theta", "", "iota"], ["theta", "iota"]),
    ],
)
def test_parse_json_or_comma_collection_variants(value: object, expected: list[str]) -> None:
    transform = None if not isinstance(value, str) or value.startswith("[") else str.upper
    result = Settings._parse_json_or_comma_collection(
        value,
        default=["fallback"],
        transform=transform,
    )

    assert result == expected


def test_parse_json_or_comma_collection_returns_fresh_default_list() -> None:
    default = ["fallback"]

    result = Settings._parse_json_or_comma_collection("", default=default)

    assert result == default
    assert result is not default


def test_parse_json_or_comma_collection_raises_on_invalid_type() -> None:
    with pytest.raises(ValueError, match="Invalid list configuration"):
        Settings._parse_json_or_comma_collection(123)


def test_load_auth_jwt_public_key_prefers_inline_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SETTINGS_SECRET_KEY", raising=False)

    inline_key = "-----BEGIN KEY-----\nabc\n-----END KEY-----"
    settings = Settings.model_validate({"THEO_AUTH_JWT_PUBLIC_KEY": inline_key})

    assert settings.load_auth_jwt_public_key() == inline_key


def test_load_auth_jwt_public_key_reads_path_when_inline_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SETTINGS_SECRET_KEY", raising=False)

    key_path = tmp_path / "token.pem"
    key_path.write_text("PEM CONTENT", encoding="utf-8")

    settings = Settings.model_validate({"THEO_AUTH_JWT_PUBLIC_KEY": str(key_path)})

    assert settings.load_auth_jwt_public_key() == "PEM CONTENT"


def test_load_auth_jwt_public_key_path_field_used_when_inline_blank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SETTINGS_SECRET_KEY", raising=False)

    key_path = tmp_path / "jwt.pem"
    key_path.write_text("JWT KEY", encoding="utf-8")

    settings = Settings.model_validate(
        {
            "THEO_AUTH_JWT_PUBLIC_KEY": "  ",
            "THEO_AUTH_JWT_PUBLIC_KEY_PATH": str(key_path),
        }
    )

    assert settings.load_auth_jwt_public_key() == "JWT KEY"


def test_load_auth_jwt_public_key_missing_file_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SETTINGS_SECRET_KEY", raising=False)

    missing_path = tmp_path / "missing.pem"

    settings = Settings.model_validate({"THEO_AUTH_JWT_PUBLIC_KEY": str(missing_path)})

    assert settings.load_auth_jwt_public_key() is None
