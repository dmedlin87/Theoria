"""Verse aggregation utilities."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import Document, Passage
from ..ingest.osis import osis_intersects
from ..models.base import Passage as PassageSchema
from ..models.verses import VerseMention, VerseMentionsFilters


def _snippet(text: str, max_length: int = 280) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def get_mentions_for_osis(
    session: Session,
    osis: str,
    filters: VerseMentionsFilters | None = None,
) -> list[VerseMention]:
    """Return passages whose OSIS reference intersects the requested range."""

    query = session.query(Passage, Document).join(Document)
    if filters:
        if filters.source_type:
            query = query.filter(Document.source_type == filters.source_type)
        if filters.collection:
            query = query.filter(Document.collection == filters.collection)

    mentions: list[VerseMention] = []
    for passage, document in query.all():
        if not passage.osis_ref:
            continue
        if not osis_intersects(passage.osis_ref, osis):
            continue

        if filters and filters.author:
            authors = document.authors or []
            if filters.author not in authors:
                continue

        base_meta = passage.meta.copy() if passage.meta else {}
        if document.title:
            base_meta.setdefault("document_title", document.title)
        if document.source_type:
            base_meta.setdefault("source_type", document.source_type)
        if document.collection:
            base_meta.setdefault("collection", document.collection)
        if document.authors:
            base_meta.setdefault("authors", document.authors)
        if document.doi:
            base_meta.setdefault("doi", document.doi)
        if document.venue:
            base_meta.setdefault("venue", document.venue)
        if document.year:
            base_meta.setdefault("year", document.year)
        if document.source_url:
            base_meta.setdefault("source_url", document.source_url)
        if document.topics is not None:
            base_meta.setdefault("topics", document.topics)
        if document.enrichment_version is not None:
            base_meta.setdefault("enrichment_version", document.enrichment_version)
        if document.provenance_score is not None:
            base_meta.setdefault("provenance_score", document.provenance_score)
        if document.bib_json and isinstance(document.bib_json, dict):
            primary_topic = document.bib_json.get("primary_topic")
            if primary_topic is not None:
                base_meta.setdefault("primary_topic", primary_topic)

        passage_schema = PassageSchema(
            id=passage.id,
            document_id=passage.document_id,
            text=passage.text,
            osis_ref=passage.osis_ref,
            page_no=passage.page_no,
            t_start=passage.t_start,
            t_end=passage.t_end,
            meta=base_meta or None,
            score=None,
        )
        mention = VerseMention(passage=passage_schema, context_snippet=_snippet(passage.text))
        mentions.append(mention)

    mentions.sort(
        key=lambda item: (
            item.passage.meta.get("document_title") if item.passage.meta else "",
            item.passage.page_no or 0,
            item.passage.t_start or 0.0,
        )
    )
    return mentions
