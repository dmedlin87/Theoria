"""Unit tests for document-related API models."""

from __future__ import annotations

import types

import pytest
from pydantic import ValidationError

from theo.infrastructure.api.app.models import documents


@pytest.fixture
def configure_ingest_settings(monkeypatch: pytest.MonkeyPatch):
    """Provide a helper for configuring ingest URL settings."""

    def _configure(*, blocked: set[str] | list[str] | tuple[str, ...] | None = None, allowed=None):
        settings = types.SimpleNamespace(
            ingest_url_blocked_schemes=blocked or [],
            ingest_url_allowed_schemes=allowed or [],
        )
        monkeypatch.setattr(documents, "get_settings", lambda: settings)

    return _configure


def test_url_ingest_request_rejects_missing_scheme(configure_ingest_settings) -> None:
    """Validation fails when the URL does not include a scheme."""

    configure_ingest_settings(blocked=[], allowed=[])

    with pytest.raises(ValidationError) as exc:
        documents.UrlIngestRequest(url="example.com/resource")

    assert "URL must include a scheme" in str(exc.value)


def test_url_ingest_request_blocks_disallowed_scheme(configure_ingest_settings) -> None:
    """Schemes listed in the blocked set are rejected regardless of allow list."""

    configure_ingest_settings(blocked={"ftp", "file"}, allowed={"http", "https"})

    with pytest.raises(ValidationError) as exc:
        documents.UrlIngestRequest(url="ftp://example.com/manual.pdf")

    assert "URL scheme is not allowed" in str(exc.value)


def test_url_ingest_request_requires_allowed_scheme(configure_ingest_settings) -> None:
    """When an allow list is defined the scheme must appear in it."""

    configure_ingest_settings(blocked=set(), allowed={"https"})

    with pytest.raises(ValidationError) as exc:
        documents.UrlIngestRequest(url="http://theoria.test/doc")

    assert "URL scheme is not allowed" in str(exc.value)


def test_url_ingest_request_accepts_allowed_scheme(configure_ingest_settings) -> None:
    """A URL with an allowed scheme passes validation."""

    configure_ingest_settings(blocked={"ftp"}, allowed={"https", "http"})

    payload = documents.UrlIngestRequest(url="https://theoria.test/notes")

    assert payload.url == "https://theoria.test/notes"


def test_simple_ingest_request_normalises_sources_from_string() -> None:
    """Newline-delimited sources are converted into a list."""

    payload = documents.SimpleIngestRequest(sources="alpha\n beta \n\n")

    assert payload.sources == ["alpha", "beta"]


def test_simple_ingest_request_requires_at_least_one_source() -> None:
    """Empty inputs raise a validation error."""

    with pytest.raises(ValidationError):
        documents.SimpleIngestRequest(sources="\n \n")


def test_simple_ingest_request_normalises_post_batch_string() -> None:
    """Comma separated post-batch entries are normalised to a list."""

    payload = documents.SimpleIngestRequest(
        sources=["alpha"],
        post_batch="notify, archive , ,",
    )

    assert payload.post_batch == ["notify", "archive"]


def test_simple_ingest_request_rejects_invalid_post_batch_type() -> None:
    """Unsupported post-batch types trigger validation errors."""

    with pytest.raises(ValidationError):
        documents.SimpleIngestRequest(sources=["alpha"], post_batch=42)


def test_document_annotation_create_harmonises_text_and_body() -> None:
    """Text is normalised and mirrored to the legacy body field."""

    payload = documents.DocumentAnnotationCreate(text="  Insightful note  ")

    assert payload.text == "Insightful note"
    assert payload.body == "Insightful note"
    assert payload.type == "note"


def test_document_annotation_create_prefers_explicit_text() -> None:
    """When both fields are supplied the text field takes precedence."""

    payload = documents.DocumentAnnotationCreate(
        text="Primary explanation",
        body="Legacy entry",
    )

    assert payload.text == "Primary explanation"
    assert payload.body == "Primary explanation"


def test_document_annotation_create_requires_content() -> None:
    """Missing text raises a validation error."""

    with pytest.raises(ValidationError):
        documents.DocumentAnnotationCreate(text=" ", body=" ")
