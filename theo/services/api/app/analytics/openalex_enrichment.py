"""Utilities for persisting OpenAlex metadata onto documents."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any, Iterable

import httpx
from sqlalchemy.orm import Session

from theo.services.api.app.persistence_models import Document
from .openalex import OpenAlexClient, _dedupe


def enrich_document_openalex_details(
    session: Session,
    document: Document,
    *,
    openalex_client: OpenAlexClient | None = None,
    max_citations: int = 50,
) -> bool:
    """Fetch and persist detailed OpenAlex metadata for a document."""

    doi, openalex_id = _document_identifiers(document)
    if not any((doi, openalex_id, document.title)):
        return False

    with ExitStack() as stack:
        client = openalex_client
        if client is None:
            client = OpenAlexClient()
            stack.callback(client.close)

        try:
            work = client.fetch_work_metadata(
                doi=doi,
                title=document.title,
                openalex_id=openalex_id,
                select=(
                    "id",
                    "doi",
                    "display_name",
                    "authorships",
                    "concepts",
                    "referenced_works",
                    "cited_by_count",
                ),
            )
        except httpx.HTTPError:
            return False

        if not isinstance(work, dict):
            return False

        resolved_id = _extract_openalex_id(work.get("id")) or openalex_id
        if not resolved_id:
            return False

        authors = _extract_authors(work.get("authorships"))
        concepts = _extract_concepts(work.get("concepts"))

        try:
            citations = client.fetch_citations(resolved_id, max_results=max_citations)
        except httpx.HTTPError:
            citations = {"referenced": [], "cited_by": []}

        updated = False
        if authors:
            document.authors = authors
            updated = True

        topics_updated = _merge_topics(document, concepts)
        updated = updated or topics_updated

        bib_json = dict(document.bib_json) if isinstance(document.bib_json, dict) else {}
        existing_openalex = bib_json.get("openalex")
        if not isinstance(existing_openalex, dict):
            existing_openalex = {}

        openalex_block = dict(existing_openalex)
        openalex_block.update(
            {
                "id": resolved_id,
                "display_name": work.get("display_name"),
                "doi": work.get("doi") or doi,
                "cited_by_count": work.get("cited_by_count"),
                "concepts": concepts,
                "authorships": work.get("authorships"),
                "referenced_works": citations.get("referenced", []),
                "cited_by": citations.get("cited_by", []),
            }
        )
        bib_json["openalex"] = openalex_block

        if authors:
            bib_json["authors"] = authors
        if citations.get("referenced"):
            bib_json["references"] = citations["referenced"]
        if citations.get("cited_by"):
            bib_json["citations"] = citations["cited_by"]

        document.bib_json = bib_json
        session.add(document)
        return updated


def _document_identifiers(document: Document) -> tuple[str | None, str | None]:
    doi: str | None = None
    openalex_id: str | None = None

    if document.doi:
        doi = document.doi

    if isinstance(document.bib_json, dict):
        doi = doi or _coerce_str(document.bib_json.get("doi"))
        doi = doi or _coerce_str(document.bib_json.get("DOI"))

        openalex_block = document.bib_json.get("openalex")
        if isinstance(openalex_block, dict):
            openalex_id = _coerce_str(openalex_block.get("id")) or openalex_id
            doi = doi or _coerce_str(openalex_block.get("doi"))

        enrichment = document.bib_json.get("enrichment")
        if isinstance(enrichment, dict):
            enriched_openalex = enrichment.get("openalex")
            if isinstance(enriched_openalex, dict):
                openalex_id = (
                    _coerce_str(enriched_openalex.get("id")) or openalex_id
                )
                doi = doi or _coerce_str(enriched_openalex.get("doi"))

    return doi, openalex_id


def _extract_authors(raw: Any) -> list[str]:
    if not isinstance(raw, Iterable):
        return []
    authors: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        author = item.get("author")
        if isinstance(author, dict):
            name = author.get("display_name")
            if isinstance(name, str) and name:
                authors.append(name)
    return _dedupe(authors)


def _extract_concepts(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, Iterable):
        return []
    concepts: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        concept = {
            key: item.get(key)
            for key in ("id", "display_name", "level", "score")
            if key in item
        }
        if concept:
            concepts.append(concept)
    return concepts


def _merge_topics(document: Document, concepts: list[dict[str, Any]]) -> bool:
    if not concepts:
        return False
    concept_names = [
        str(concept.get("display_name"))
        for concept in concepts
        if isinstance(concept.get("display_name"), str)
    ]
    concept_names = [name for name in concept_names if name]
    if not concept_names:
        return False

    preserve_mapping = isinstance(document.topics, dict)
    existing_primary: str | None = None

    if isinstance(document.topics, list):
        existing_topics = [str(item) for item in document.topics if item]
    elif isinstance(document.topics, dict):
        mapping = document.topics
        all_values = mapping.get("all")
        if isinstance(all_values, list):
            existing_topics = [str(item) for item in all_values if item]
        else:
            existing_topics = [str(value) for value in mapping.values() if value]
        primary = mapping.get("primary")
        existing_primary = str(primary) if isinstance(primary, str) and primary else None
    else:
        existing_topics = []

    merged = _dedupe(existing_topics + concept_names)
    if merged == existing_topics:
        return False

    if preserve_mapping:
        primary_topic = existing_primary or (merged[0] if merged else None)
        document.topics = {
            "primary": primary_topic,
            "all": merged,
        }
        existing_primary = primary_topic
    else:
        document.topics = merged

    if isinstance(document.bib_json, dict):
        topics = list(document.bib_json.get("topics") or [])
    else:
        topics = []
    merged_topics = _dedupe(list(topics) + concept_names)
    bib_json = dict(document.bib_json) if isinstance(document.bib_json, dict) else {}
    bib_json["topics"] = merged_topics
    primary_value = existing_primary or (concept_names[0] if concept_names else None)
    if primary_value:
        bib_json.setdefault("primary_topic", primary_value)
    document.bib_json = bib_json
    return True


def _extract_openalex_id(raw: Any) -> str | None:
    value = _coerce_str(raw)
    if not value:
        return None
    prefix = "https://openalex.org/"
    if value.startswith(prefix):
        value = value[len(prefix) :]
    return value or None


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


__all__ = ["enrich_document_openalex_details"]
