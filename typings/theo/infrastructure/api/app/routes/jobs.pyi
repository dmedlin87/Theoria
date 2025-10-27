from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from theo.infrastructure.api.app.models.jobs import HNSWRefreshJobRequest


class JobStatus:
    def model_dump(self) -> dict[str, Any]: ...


def enqueue_refresh_hnsw_job(
    job_request: HNSWRefreshJobRequest,
    *,
    session: Session | None = ...,
) -> JobStatus: ...


__all__ = ["JobStatus", "enqueue_refresh_hnsw_job"]
