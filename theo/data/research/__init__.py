"""Resource helpers for bundled research datasets."""
from __future__ import annotations

from importlib import resources
from typing import BinaryIO, TextIO

__all__ = ["files", "open_binary", "open_text", "read_binary", "read_text"]


def files() -> resources.abc.Traversable:
    """Return the traversable representing bundled research data files."""

    return resources.files(__name__)


def open_binary(name: str) -> BinaryIO:
    """Open a bundled research data file in binary mode."""

    return files().joinpath(name).open("rb")


def open_text(name: str, encoding: str = "utf-8") -> TextIO:
    """Open a bundled research data file in text mode."""

    return files().joinpath(name).open("r", encoding=encoding)


def read_binary(name: str) -> bytes:
    """Read the entire contents of a bundled binary resource."""

    with open_binary(name) as handle:
        return handle.read()


def read_text(name: str, encoding: str = "utf-8") -> str:
    """Read the entire contents of a bundled text resource."""

    with open_text(name, encoding=encoding) as handle:
        return handle.read()
