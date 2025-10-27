"""Unit tests for the shared SQLAlchemy repository helpers."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from theo.adapters.persistence.base_repository import BaseRepository


class DummyModel:
    """Simple stand-in for ORM models used in helper tests."""


@pytest.fixture
def session():
    """Return a mock SQLAlchemy session."""

    return Mock()


@pytest.fixture
def repository(session):
    """Instantiate the base repository with a mock session."""

    return BaseRepository[DummyModel](session)


def test_session_property_exposes_underlying_session(repository, session):
    """The ``session`` property should return the provided session."""

    assert repository.session is session


def test_add_and_add_all_delegate_to_session(repository, session):
    """``add`` and ``add_all`` forward to the wrapped session."""

    instance = DummyModel()
    repository.add(instance)
    session.add.assert_called_once_with(instance)

    other_instances = [DummyModel(), DummyModel()]
    returned = repository.add_all(other_instances)
    session.add_all.assert_called_once_with(other_instances)
    assert returned == other_instances


def test_add_all_handles_empty_iterables(repository, session):
    """Empty iterables should not trigger a call to ``session.add_all``."""

    returned = repository.add_all([])
    session.add_all.assert_not_called()
    assert returned == []


def test_delete_and_flush_helpers(repository, session):
    """Deletion and flush operations reuse the underlying session."""

    instance = DummyModel()
    repository.delete(instance)
    session.delete.assert_called_once_with(instance)

    repository.flush()
    session.flush.assert_called_once_with()


def test_refresh_and_get_helpers(repository, session):
    """The refresh/get helpers should proxy to the SQLAlchemy session."""

    instance = DummyModel()
    repository.refresh(instance)
    session.refresh.assert_called_once_with(instance)

    repository.get(DummyModel, "identifier")
    session.get.assert_called_once_with(DummyModel, "identifier")


def test_execute_and_scalar_helpers(repository, session):
    """Execution and scalar helpers provide convenient delegation."""

    statement = Mock(name="statement")
    repository.execute(statement)
    session.execute.assert_called_once_with(statement)

    scalar_result = Mock(name="scalar_result")
    session.scalars.return_value = scalar_result

    repository.scalars(statement)
    session.scalars.assert_called_with(statement)

    repository.scalar_first(statement)
    scalar_result.first.assert_called_once_with()

    repository.scalar_one_or_none(statement)
    scalar_result.one_or_none.assert_called_once_with()

    scalar_result.__iter__ = Mock(return_value=iter([1, 2]))
    assert repository.scalar_all(statement) == [1, 2]

