"""Minimal pytest plugin compat shim for the local :mod:`faker` stub.

The real ``Faker`` distribution used to expose ``faker.contrib.pytest`` to
provide a ``faker`` fixture.  Our repository ships a lightweight stand-in
for the library that intentionally only implements the surface area our
tests exercise.  Recent upstream releases removed the contrib module,
which means the entry point declared in the distribution now resolves to
this stub package and pytest attempts to import a module that no longer
exists.

Providing this module keeps the auto-discovered plugin importable so that
pytest startup does not crash, and it offers a tiny ``faker`` fixture that
mirrors the behaviour relied upon by our tests (a seeded instance with a
reset random state per invocation).
"""

from __future__ import annotations

import pytest

from ...config import DEFAULT_LOCALE  # noqa: F401 - kept for compatibility
from ... import Faker

DEFAULT_SEED = 0


@pytest.fixture(scope="session", autouse=True)
def _session_faker() -> Faker:
    """Session-level ``Faker`` instance to match the upstream API."""

    fake = Faker()
    fake.seed_instance(DEFAULT_SEED)
    return fake


@pytest.fixture()
def faker(request: pytest.FixtureRequest) -> Faker:
    """Return a freshly seeded ``Faker`` instance for each test."""

    seed = DEFAULT_SEED
    if "faker_seed" in request.fixturenames:
        seed = request.getfixturevalue("faker_seed")

    fake = Faker()
    fake.seed_instance(seed)
    return fake
