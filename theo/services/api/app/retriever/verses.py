"""Verse aggregator retrieval helpers."""

from ..models.verses import VerseMention


def get_mentions_for_osis(osis: str) -> list[VerseMention]:
    """Return placeholder mentions for the requested OSIS reference."""

    return []
