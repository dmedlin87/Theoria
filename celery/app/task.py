"""Simplified Celery :class:`Task` implementation used in tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Callable, Iterable

from ..exceptions import Retry


@dataclass
class _TaskResult:
    result: Any


@dataclass
class Task:
    """Wrap a callable while emulating the Celery task API surface."""

    func: Callable[..., Any]
    app: Any
    name: str
    bind: bool = False
    max_retries: int = 3
    __name__: str = field(init=False)
    __doc__: str | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.__name__ = getattr(self.func, "__name__", self.name)
        self.__doc__ = getattr(self.func, "__doc__", None)
        self.request = SimpleNamespace(
            retries=0,
            is_eager=True,
            called_directly=True,
            delivery_info={},
        )

    def run(self, *args: Any, **kwargs: Any) -> Any:
        if self.bind:
            return self.func(self, *args, **kwargs)
        return self.func(*args, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - thin alias
        return self.run(*args, **kwargs)

    def apply(self, args: Iterable[Any] | None = None, kwargs: dict[str, Any] | None = None) -> _TaskResult:
        self.request.retries = 0
        call_args = tuple(args or ())
        call_kwargs = dict(kwargs or {})
        self.request.args = call_args
        self.request.kwargs = call_kwargs
        result = self.run(*call_args, **call_kwargs)
        return _TaskResult(result=result)

    def apply_async(
        self,
        args: Iterable[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        **_options: Any,
    ) -> _TaskResult:
        return self.apply(args=args, kwargs=kwargs)

    delay = apply_async

    def retry(
        self,
        *_,
        exc: BaseException | None = None,
        countdown: float | None = None,
        **__,
    ) -> None:
        raise Retry("Task retry requested", exc=exc, when=countdown)

    def signature_from_request(
        self,
        request: SimpleNamespace,
        args: Iterable[Any] | None,
        kwargs: dict[str, Any] | None,
        *,
        countdown: float | None = None,
        eta: float | None = None,
        retries: int | None = None,
    ) -> SimpleNamespace:
        resolved_args = tuple(args) if args is not None else tuple(getattr(request, "args", ()))
        resolved_kwargs = dict(kwargs) if kwargs is not None else dict(getattr(request, "kwargs", {}))
        return SimpleNamespace(
            args=resolved_args,
            kwargs=resolved_kwargs,
            countdown=countdown,
            eta=eta,
            retries=retries if retries is not None else getattr(request, "retries", 0),
        )
