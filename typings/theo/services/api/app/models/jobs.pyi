from __future__ import annotations

from typing import Any


class HNSWRefreshJobRequest:
    sample_queries: int
    top_k: int

    def __init__(
        self,
        *,
        sample_queries: int = ...,
        top_k: int = ...,
    ) -> None: ...

    def model_dump(self) -> dict[str, Any]: ...


__all__ = ["HNSWRefreshJobRequest"]
