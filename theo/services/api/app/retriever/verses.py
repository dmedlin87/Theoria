"""Verse aggregation utilities."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import Passage
from ..ingest.osis import osis_intersects
from ..models.base import Passage as PassageSchema
from ..models.verses import VerseMention


def get_mentions_for_osis(session: Session, osis: str) -> list[VerseMention]:
    """Return passages whose OSIS reference intersects the requested range."""

    rows = session.query(Passage).all()
    mentions: list[VerseMention] = []
    for passage in rows:
        if not passage.osis_ref:
            continue
        if not osis_intersects(passage.osis_ref, osis):
            continue
        passage_schema = PassageSchema(
            id=passage.id,
            document_id=passage.document_id,
            text=passage.text,
            osis_ref=passage.osis_ref,
            page_no=passage.page_no,
            t_start=passage.t_start,
            t_end=passage.t_end,
            meta=passage.meta,
            score=None,
        )
        context = passage.text
        mention = VerseMention(passage=passage_schema, context_snippet=context)
        mentions.append(mention)

    mentions.sort(key=lambda item: item.passage.page_no or 0)
    return mentions
