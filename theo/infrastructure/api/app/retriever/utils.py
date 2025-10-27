"""Shared helpers for retrieval pipelines."""

from __future__ import annotations

from typing import Any

from theo.infrastructure.api.app.persistence_models import Document, Passage


def compose_passage_meta(passage: Passage, document: Document) -> dict[str, Any] | None:
    """Merge document context with passage metadata for client consumption."""

    meta: dict[str, Any] = {}

    if document.title:
        meta["document_title"] = document.title
    if document.source_type:
        meta["source_type"] = document.source_type
    if document.collection:
        meta["collection"] = document.collection
    if document.authors:
        meta["authors"] = document.authors
    if document.doi:
        meta["doi"] = document.doi
    if document.venue:
        meta["venue"] = document.venue
    if document.year is not None:
        meta["year"] = document.year
    if document.source_url:
        meta["source_url"] = document.source_url
    if document.topics is not None:
        meta["topics"] = document.topics
    if document.theological_tradition:
        meta["theological_tradition"] = document.theological_tradition
    if document.topic_domains:
        meta["topic_domains"] = document.topic_domains
    if document.enrichment_version is not None:
        meta["enrichment_version"] = document.enrichment_version
    if document.provenance_score is not None:
        meta["provenance_score"] = document.provenance_score
    if document.bib_json and isinstance(document.bib_json, dict):
        primary_topic = document.bib_json.get("primary_topic")
        if primary_topic is not None:
            meta.setdefault("primary_topic", primary_topic)

    if passage.meta:
        meta.update(passage.meta)

    return meta or None
