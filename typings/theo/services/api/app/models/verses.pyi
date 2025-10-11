from __future__ import annotations


class VerseMentionsFilters:
    source_type: str | None
    collection: str | None
    author: str | None

    def __init__(self, **kwargs: object) -> None: ...


__all__ = ["VerseMentionsFilters"]
