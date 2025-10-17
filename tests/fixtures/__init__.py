"""Reusable factories and seeded fixtures for regression tests."""

from .regression_factory import (
    DocumentRecord,
    PassageRecord,
    RegressionDataFactory,
)

__all__ = [
    "DocumentRecord",
    "PassageRecord",
    "RegressionDataFactory",
]
