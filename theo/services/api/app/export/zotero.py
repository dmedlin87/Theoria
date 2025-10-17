"""Zotero integration for exporting citations."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Mapping, Sequence

import httpx

from .citations import CitationSource

LOGGER = logging.getLogger(__name__)

ZOTERO_API_BASE = "https://api.zotero.org"
ZOTERO_ITEM_VERSION = 3


class ZoteroExportError(Exception):
    """Raised when Zotero export fails."""

    pass


def _build_zotero_item(
    source: CitationSource, csl_entry: dict[str, Any]
) -> dict[str, Any]:
    """Convert a citation source to Zotero item format.

    Zotero uses a specific JSON schema for items. This maps our CSL data
    to Zotero's format.

    Args:
        source: Normalized citation source
        csl_entry: CSL-JSON representation

    Returns:
        Zotero-formatted item dictionary
    """
    # Determine item type
    csl_type = csl_entry.get("type", "article-journal")
    item_type = _map_csl_to_zotero_type(csl_type)

    # Build creators list (authors)
    creators: list[dict[str, str]] = []
    if "author" in csl_entry:
        for author in csl_entry["author"]:
            creator: dict[str, str] = {"creatorType": "author"}
            if "family" in author and "given" in author:
                creator["lastName"] = author["family"]
                creator["firstName"] = author["given"]
            elif "literal" in author:
                creator["name"] = author["literal"]
            else:
                continue
            creators.append(creator)

    # Build base item
    item: dict[str, Any] = {
        "itemType": item_type,
        "title": source.title or "Untitled",
        "creators": creators,
    }

    # Add optional fields based on item type
    if source.year:
        item["date"] = str(source.year)

    if source.abstract:
        item["abstractNote"] = source.abstract

    if source.doi:
        item["DOI"] = source.doi

    if source.source_url:
        item["url"] = source.source_url

    # Journal article fields
    if item_type == "journalArticle":
        if source.venue:
            item["publicationTitle"] = source.venue
        if source.volume:
            item["volume"] = str(source.volume)
        if source.issue:
            item["issue"] = str(source.issue)
        if source.pages:
            item["pages"] = source.pages

    # Book fields
    elif item_type == "book":
        if source.publisher:
            item["publisher"] = source.publisher
        if source.location:
            item["place"] = source.location
        if source.collection:
            item["series"] = source.collection

    # Book section fields
    elif item_type == "bookSection":
        if source.collection:
            item["bookTitle"] = source.collection
        if source.publisher:
            item["publisher"] = source.publisher
        if source.location:
            item["place"] = source.location
        if source.pages:
            item["pages"] = source.pages

    # Add tags from topics
    if source.topics:
        item["tags"] = [{"tag": topic} for topic in source.topics]

    # Add notes for anchors and metadata
    notes: list[str] = []
    if source.metadata:
        anchors = source.metadata.get("anchors")
        if anchors:
            notes.append(f"Anchors: {anchors}")

    if notes:
        item["notes"] = [{"note": note} for note in notes]

    return item


def _map_csl_to_zotero_type(csl_type: str) -> str:
    """Map CSL item types to Zotero item types.

    Args:
        csl_type: CSL item type string

    Returns:
        Zotero item type string
    """
    mapping = {
        "article-journal": "journalArticle",
        "article-magazine": "magazineArticle",
        "article-newspaper": "newspaperArticle",
        "book": "book",
        "chapter": "bookSection",
        "paper-conference": "conferencePaper",
        "thesis": "thesis",
        "manuscript": "manuscript",
        "report": "report",
        "webpage": "webpage",
        "motion_picture": "videoRecording",
        "song": "audioRecording",
        "speech": "presentation",
    }
    return mapping.get(csl_type, "journalArticle")


async def export_to_zotero(
    sources: Sequence[CitationSource],
    csl_entries: Sequence[dict[str, Any]],
    api_key: str,
    user_id: str | None = None,
    group_id: str | None = None,
) -> dict[str, Any]:
    """Export citation sources to Zotero library.

    Uses the Zotero Write API to create items in a user's library.
    Requires a valid Zotero API key with write permissions.

    Args:
        sources: List of citation sources to export
        csl_entries: Corresponding CSL-JSON entries
        api_key: Zotero API key with write access
        user_id: Zotero user ID (if personal library)
        group_id: Zotero group ID (if group library)

    Returns:
        Dictionary with export results:
        - success: bool
        - exported_count: int
        - failed_count: int
        - errors: list of error messages

    Raises:
        ZoteroExportError: If export fails critically
    """
    if not api_key or not api_key.strip():
        raise ZoteroExportError("Zotero API key is required")

    if not user_id and not group_id:
        raise ZoteroExportError("Either user_id or group_id must be provided")

    if len(sources) != len(csl_entries):
        raise ZoteroExportError("Sources and CSL entries must have same length")

    # Build Zotero items
    items = []
    for source, csl_entry in zip(sources, csl_entries):
        try:
            item = _build_zotero_item(source, csl_entry)
            items.append(item)
        except Exception as exc:
            LOGGER.warning(
                "Failed to build Zotero item for document %s: %s",
                source.document_id,
                exc,
            )
            continue

    if not items:
        return {
            "success": False,
            "exported_count": 0,
            "failed_count": len(sources),
            "errors": ["Failed to build any Zotero items"],
        }

    # Determine library endpoint
    if user_id:
        endpoint = f"{ZOTERO_API_BASE}/users/{user_id}/items"
    else:
        endpoint = f"{ZOTERO_API_BASE}/groups/{group_id}/items"

    # Make API request
    headers = {
        "Zotero-API-Key": api_key,
        "Content-Type": "application/json",
        "Zotero-API-Version": str(ZOTERO_ITEM_VERSION),
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(endpoint, json=items, headers=headers)

            if response.status_code == 200:
                result = response.json()
                if inspect.isawaitable(result):
                    result = await result
                successful = result.get("successful", {})
                failed = result.get("failed", {})

                return {
                    "success": True,
                    "exported_count": len(successful),
                    "failed_count": len(failed),
                    "errors": list(failed.values()) if failed else [],
                }
            elif response.status_code == 403:
                raise ZoteroExportError(
                    "Access denied. Check that your API key has write permissions."
                )
            elif response.status_code == 404:
                raise ZoteroExportError(
                    "Library not found. Check that user_id or group_id is correct."
                )
            else:
                error_text = response.text
                raise ZoteroExportError(
                    f"Zotero API request failed with status {response.status_code}: {error_text}"
                )

    except httpx.TimeoutException as exc:
        raise ZoteroExportError("Request to Zotero API timed out") from exc
    except httpx.HTTPError as exc:
        raise ZoteroExportError(f"HTTP error contacting Zotero API: {exc}") from exc


async def verify_zotero_credentials(
    api_key: str, user_id: str | None = None, group_id: str | None = None
) -> bool:
    """Verify that Zotero API credentials are valid.

    Makes a lightweight GET request to check access.

    Args:
        api_key: Zotero API key
        user_id: Zotero user ID (if personal library)
        group_id: Zotero group ID (if group library)

    Returns:
        True if credentials are valid, False otherwise
    """
    if not api_key or not api_key.strip():
        return False

    if not user_id and not group_id:
        return False

    # Determine library endpoint
    if user_id:
        endpoint = f"{ZOTERO_API_BASE}/users/{user_id}/items"
    else:
        endpoint = f"{ZOTERO_API_BASE}/groups/{group_id}/items"

    headers = {
        "Zotero-API-Key": api_key,
        "Zotero-API-Version": str(ZOTERO_ITEM_VERSION),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                endpoint, headers=headers, params={"limit": 1}
            )
            return response.status_code == 200
    except Exception as exc:
        LOGGER.debug("Zotero credential verification failed: %s", exc)
        return False


__all__ = [
    "ZoteroExportError",
    "export_to_zotero",
    "verify_zotero_credentials",
]
