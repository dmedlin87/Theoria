"""Tests for Zotero export integration."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from theo.infrastructure.api.app.export.zotero import (
    ZoteroExportError,
    export_to_zotero,
    verify_zotero_credentials,
    _build_zotero_item,
    _map_csl_to_zotero_type,
)
from theo.infrastructure.api.app.export.citations import CitationSource


@pytest.fixture
def sample_source():
    """Sample citation source for testing."""
    return CitationSource(
        document_id="doc-123",
        title="Systematic Theology",
        authors=["John Calvin", "Jane Doe"],
        year=2020,
        venue="Theological Journal",
        publisher="Academic Press",
        location="Grand Rapids",
        volume="15",
        issue="3",
        pages="123-145",
        doi="10.1234/theology.2020",
        source_url="https://example.com/doc",
        abstract="A comprehensive study of Reformed theology.",
        topics=["Soteriology", "Christology"],
    )


@pytest.fixture
def sample_csl_entry():
    """Sample CSL entry for testing."""
    return {
        "id": "doc-123",
        "type": "article-journal",
        "title": "Systematic Theology",
        "author": [
            {"family": "Calvin", "given": "John"},
            {"family": "Doe", "given": "Jane"},
        ],
        "issued": {"date-parts": [[2020]]},
        "container-title": "Theological Journal",
        "volume": "15",
        "issue": "3",
        "page": "123-145",
        "DOI": "10.1234/theology.2020",
        "URL": "https://example.com/doc",
        "abstract": "A comprehensive study of Reformed theology.",
    }


def test_map_csl_to_zotero_type():
    """Test CSL to Zotero type mapping."""
    assert _map_csl_to_zotero_type("article-journal") == "journalArticle"
    assert _map_csl_to_zotero_type("book") == "book"
    assert _map_csl_to_zotero_type("chapter") == "bookSection"
    assert _map_csl_to_zotero_type("webpage") == "webpage"
    assert _map_csl_to_zotero_type("unknown-type") == "journalArticle"


def test_build_zotero_item_journal_article(sample_source, sample_csl_entry):
    """Test building Zotero item from journal article."""
    item = _build_zotero_item(sample_source, sample_csl_entry)

    assert item["itemType"] == "journalArticle"
    assert item["title"] == "Systematic Theology"
    assert item["date"] == "2020"
    assert item["publicationTitle"] == "Theological Journal"
    assert item["volume"] == "15"
    assert item["issue"] == "3"
    assert item["pages"] == "123-145"
    assert item["DOI"] == "10.1234/theology.2020"
    assert item["url"] == "https://example.com/doc"
    assert item["abstractNote"] == "A comprehensive study of Reformed theology."

    # Check creators
    assert len(item["creators"]) == 2
    assert item["creators"][0] == {
        "creatorType": "author",
        "firstName": "John",
        "lastName": "Calvin",
    }
    assert item["creators"][1] == {
        "creatorType": "author",
        "firstName": "Jane",
        "lastName": "Doe",
    }

    # Check tags
    assert len(item["tags"]) == 2
    assert {"tag": "Soteriology"} in item["tags"]
    assert {"tag": "Christology"} in item["tags"]


def test_build_zotero_item_book():
    """Test building Zotero item from book."""
    source = CitationSource(
        document_id="book-1",
        title="Commentary on Romans",
        authors=["Martin Luther"],
        year=1516,
        publisher="Wittenberg Press",
        location="Wittenberg",
        source_type="book",
    )

    csl_entry = {
        "id": "book-1",
        "type": "book",
        "title": "Commentary on Romans",
        "author": [{"family": "Luther", "given": "Martin"}],
        "issued": {"date-parts": [[1516]]},
        "publisher": "Wittenberg Press",
        "publisher-place": "Wittenberg",
    }

    item = _build_zotero_item(source, csl_entry)

    assert item["itemType"] == "book"
    assert item["title"] == "Commentary on Romans"
    assert item["date"] == "1516"
    assert item["publisher"] == "Wittenberg Press"
    assert item["place"] == "Wittenberg"


def test_build_zotero_item_minimal_data():
    """Test building Zotero item with minimal data."""
    source = CitationSource(
        document_id="minimal-doc",
        title="Untitled Work",
    )

    csl_entry = {
        "id": "minimal-doc",
        "type": "article-journal",
        "title": "Untitled Work",
    }

    item = _build_zotero_item(source, csl_entry)

    assert item["itemType"] == "journalArticle"
    assert item["title"] == "Untitled Work"
    assert item["creators"] == []


def test_build_zotero_item_literal_author():
    """Test handling literal author names."""
    source = CitationSource(
        document_id="org-doc",
        title="Church Statement",
        authors=["World Council of Churches"],
    )

    csl_entry = {
        "id": "org-doc",
        "type": "article-journal",
        "title": "Church Statement",
        "author": [{"literal": "World Council of Churches"}],
    }

    item = _build_zotero_item(source, csl_entry)

    assert len(item["creators"]) == 1
    assert item["creators"][0] == {
        "creatorType": "author",
        "name": "World Council of Churches",
    }


@pytest.mark.asyncio
async def test_export_to_zotero_success(sample_source, sample_csl_entry):
    """Test successful export to Zotero."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "successful": {"0": "ABC123"},
        "failed": {},
    }

    with patch("theo.infrastructure.api.app.export.zotero.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        result = await export_to_zotero(
            sources=[sample_source],
            csl_entries=[sample_csl_entry],
            api_key="test-api-key",
            user_id="12345",
        )

    assert result["success"] is True
    assert result["exported_count"] == 1
    assert result["failed_count"] == 0
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_export_to_zotero_partial_failure(sample_source, sample_csl_entry):
    """Test Zotero export with partial failures."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "successful": {"0": "ABC123"},
        "failed": {"1": "Invalid item format"},
    }

    with patch("theo.infrastructure.api.app.export.zotero.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        result = await export_to_zotero(
            sources=[sample_source, sample_source],
            csl_entries=[sample_csl_entry, sample_csl_entry],
            api_key="test-api-key",
            user_id="12345",
        )

    assert result["success"] is True
    assert result["exported_count"] == 1
    assert result["failed_count"] == 1
    assert len(result["errors"]) == 1


@pytest.mark.asyncio
async def test_export_to_zotero_missing_api_key():
    """Test Zotero export without API key."""
    with pytest.raises(ZoteroExportError, match="API key is required"):
        await export_to_zotero(
            sources=[],
            csl_entries=[],
            api_key="",
            user_id="12345",
        )


@pytest.mark.asyncio
async def test_export_to_zotero_missing_target():
    """Test Zotero export without user_id or group_id."""
    with pytest.raises(ZoteroExportError, match="Either user_id or group_id"):
        await export_to_zotero(
            sources=[],
            csl_entries=[],
            api_key="test-key",
        )


@pytest.mark.asyncio
async def test_export_to_zotero_length_mismatch():
    """Test Zotero export with mismatched sources and CSL entries."""
    with pytest.raises(ZoteroExportError, match="same length"):
        await export_to_zotero(
            sources=[CitationSource(document_id="doc-1")],
            csl_entries=[{}, {}],
            api_key="test-key",
            user_id="12345",
        )


@pytest.mark.asyncio
async def test_export_to_zotero_forbidden(sample_source, sample_csl_entry):
    """Test Zotero export with invalid credentials."""
    mock_response = AsyncMock()
    mock_response.status_code = 403
    mock_response.text = "Forbidden"

    with patch("theo.infrastructure.api.app.export.zotero.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        with pytest.raises(ZoteroExportError, match="Access denied"):
            await export_to_zotero(
                sources=[sample_source],
                csl_entries=[sample_csl_entry],
                api_key="invalid-key",
                user_id="12345",
            )


@pytest.mark.asyncio
async def test_export_to_zotero_not_found(sample_source, sample_csl_entry):
    """Test Zotero export with invalid library ID."""
    mock_response = AsyncMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    with patch("theo.infrastructure.api.app.export.zotero.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        with pytest.raises(ZoteroExportError, match="Library not found"):
            await export_to_zotero(
                sources=[sample_source],
                csl_entries=[sample_csl_entry],
                api_key="test-key",
                user_id="99999",
            )


@pytest.mark.asyncio
async def test_export_to_zotero_timeout(sample_source, sample_csl_entry):
    """Test Zotero export with timeout."""
    import httpx

    with patch("theo.infrastructure.api.app.export.zotero.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        with pytest.raises(ZoteroExportError, match="timed out"):
            await export_to_zotero(
                sources=[sample_source],
                csl_entries=[sample_csl_entry],
                api_key="test-key",
                user_id="12345",
            )


@pytest.mark.asyncio
async def test_export_to_zotero_group_library(sample_source, sample_csl_entry):
    """Test export to group library instead of personal library."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "successful": {"0": "ABC123"},
        "failed": {},
    }

    with patch("theo.infrastructure.api.app.export.zotero.httpx.AsyncClient") as mock_client:
        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await export_to_zotero(
            sources=[sample_source],
            csl_entries=[sample_csl_entry],
            api_key="test-api-key",
            group_id="67890",
        )

    # Verify it called the group endpoint
    call_args = mock_post.call_args
    assert "groups/67890/items" in call_args[0][0]
    assert result["success"] is True


@pytest.mark.asyncio
async def test_verify_zotero_credentials_valid():
    """Test successful Zotero credential verification."""
    mock_response = AsyncMock()
    mock_response.status_code = 200

    with patch("theo.infrastructure.api.app.export.zotero.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        result = await verify_zotero_credentials(
            api_key="valid-key",
            user_id="12345",
        )

    assert result is True


@pytest.mark.asyncio
async def test_verify_zotero_credentials_invalid():
    """Test failed Zotero credential verification."""
    mock_response = AsyncMock()
    mock_response.status_code = 403

    with patch("theo.infrastructure.api.app.export.zotero.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        result = await verify_zotero_credentials(
            api_key="invalid-key",
            user_id="12345",
        )

    assert result is False


@pytest.mark.asyncio
async def test_verify_zotero_credentials_missing_params():
    """Test credential verification without required params."""
    result = await verify_zotero_credentials(api_key="", user_id="12345")
    assert result is False

    result = await verify_zotero_credentials(api_key="key", user_id=None, group_id=None)
    assert result is False
