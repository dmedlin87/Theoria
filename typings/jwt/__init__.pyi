from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence, Type

class PyJWTError(Exception):
    ...


class DecodeError(PyJWTError):
    ...


class InvalidTokenError(DecodeError):
    ...


class ExpiredSignatureError(InvalidTokenError):
    ...


def encode(
    payload: Mapping[str, Any],
    key: str,
    algorithm: str = ...,
    headers: Mapping[str, Any] | None = ...,
    json_encoder: Type[Any] | None = ...,
) -> str:
    ...


def decode(
    jwt: str,
    key: str | None = ...,
    algorithms: Iterable[str] | str | None = ...,
    options: Mapping[str, Any] | None = ...,
    audience: str | Sequence[str] | None = ...,
    issuer: str | None = ...,
    leeway: int | float | None = ...,
    **kwargs: Any,
) -> dict[str, Any]:
    ...


__all__ = [
    "PyJWTError",
    "DecodeError",
    "InvalidTokenError",
    "ExpiredSignatureError",
    "encode",
    "decode",
]
