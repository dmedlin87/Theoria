from __future__ import annotations

import string
from collections.abc import Sequence

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import DrawFn, composite
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from theo.adapters.persistence.models import Base, IngestionJob
from theo.infrastructure.api.app.workers import tasks


@composite
def _job_updates(draw: DrawFn) -> Sequence[dict[str, str | None]]:
    status = st.text(alphabet=string.ascii_letters, min_size=3, max_size=18)
    optional_text = st.one_of(
        st.none(), st.text(alphabet=string.ascii_letters + string.digits, max_size=24)
    )
    updates = draw(
        st.lists(
            st.fixed_dictionaries(
                {
                    "status": status,
                    "error": optional_text,
                    "document_id": optional_text,
                }
            ),
            min_size=1,
            max_size=6,
        )
    )
    return updates


@given(_job_updates())
@settings(max_examples=15)
def test_update_job_status_is_idempotent(updates: Sequence[dict[str, str | None]]) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        job = IngestionJob(job_type="pytest", status="queued")
        session.add(job)
        session.commit()
        job_id = job.id

    timestamps: list[float] = []
    with Session(engine) as session:
        for update in updates:
            tasks._update_job_status(
                session,
                job_id,
                status=update["status"],
                error=update["error"],
                document_id=update["document_id"],
            )
            session.flush()
            persisted = session.get(IngestionJob, job_id)
            assert persisted is not None
            timestamps.append(persisted.updated_at.timestamp())
        session.commit()

    with Session(engine) as session:
        persisted = session.get(IngestionJob, job_id)
        assert persisted is not None

    last_error = next(
        (update["error"] for update in reversed(updates) if update["error"] is not None),
        None,
    )
    last_document = next(
        (
            update["document_id"]
            for update in reversed(updates)
            if update["document_id"] is not None
        ),
        None,
    )

    assert persisted.status == updates[-1]["status"]
    assert persisted.error == last_error
    assert persisted.document_id == last_document
    assert timestamps == sorted(timestamps)

    engine.dispose()


@given(st.integers(min_value=-2, max_value=10))
@settings(max_examples=20)
def test_retry_backoff_bounded(retries: int) -> None:
    delay = tasks._compute_retry_delay(retries)
    assert 1 <= delay <= 60
    if retries <= 0:
        assert delay == 1
    elif retries >= 6:
        assert delay == 60
    else:
        assert delay == 2**retries


@given(
    st.integers(min_value=0, max_value=10), st.integers(min_value=0, max_value=10)
)
@settings(max_examples=20)
def test_retry_backoff_monotonicity(lhs: int, rhs: int) -> None:
    smaller, larger = sorted((lhs, rhs))
    assert tasks._compute_retry_delay(smaller) <= tasks._compute_retry_delay(larger)
