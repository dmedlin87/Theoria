"""Exception hierarchy stubs for the in-repo Celery shim."""

from __future__ import annotations


class Retry(Exception):
    """Mirror :class:`celery.exceptions.Retry` for lightweight environments."""

    def __init__(
        self,
        message: str | None = None,
        *,
        exc: BaseException | None = None,
        when: float | None = None,
        is_eager: bool | None = None,
        sig: object | None = None,
    ) -> None:
        super().__init__(message)
        self.exc = exc
        self.when = when
        self.is_eager = is_eager
        self.sig = sig


__all__ = ["Retry"]
