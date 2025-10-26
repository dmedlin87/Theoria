"""Logging helpers compatible with Celery's test fixtures."""

from __future__ import annotations

import logging


def get_task_logger(name: str) -> logging.Logger:
    """Return a module-level logger configured for worker tasks."""

    return logging.getLogger(name)


__all__ = ["get_task_logger"]
