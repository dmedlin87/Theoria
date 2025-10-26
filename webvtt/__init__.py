"""Minimal WebVTT parser used for worker tests.

The real :mod:`webvtt` dependency pulls in a number of optional packages.  The
worker suites only rely on a tiny subset of its functionality (parsing timestamps
and yielding caption entries), so we provide a lightweight pure-Python
implementation that covers the project fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Iterator, List

_TIMESTAMP_RE = re.compile(
    r"^(?:(?P<hours>\d+):)?(?P<minutes>[0-5]?\d):(?P<seconds>[0-5]?\d)[\.,](?P<millis>\d{1,3})$"
)


def _parse_timestamp(value: str) -> float:
    match = _TIMESTAMP_RE.match(value.strip())
    if not match:  # pragma: no cover - defensive branch for malformed cues
        raise ValueError(f"Invalid timestamp: {value!r}")
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    millis = int(match.group("millis").ljust(3, "0"))
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


@dataclass(slots=True)
class Caption:
    start: str
    end: str
    text: str

    @property
    def start_in_seconds(self) -> float:
        return _parse_timestamp(self.start)

    @property
    def end_in_seconds(self) -> float:
        return _parse_timestamp(self.end)


def _iter_cues(lines: Iterable[str]) -> Iterator[Caption]:
    start: str | None = None
    end: str | None = None
    payload: List[str] = []

    def emit() -> Iterator[Caption]:
        nonlocal start, end, payload
        if start is None or end is None:
            return
        text = "\n".join(payload).strip()
        yield Caption(start=start, end=end, text=text)
        start = None
        end = None
        payload = []

    for raw_line in lines:
        line = raw_line.strip("\ufeff\n\r")
        if not line:
            yield from emit()
            continue

        if line.upper().startswith("WEBVTT"):
            continue
        if line.isdigit():
            # Cue index, ignore and continue reading timestamps.
            continue
        if "-->" in line:
            parts = [part.strip() for part in line.split("-->", 1)]
            if len(parts) == 2:
                start, end = parts
                payload = []
            continue

        payload.append(line)

    yield from emit()


def read(path: str) -> list[Caption]:
    with open(path, encoding="utf-8") as handle:
        return list(_iter_cues(handle))


def from_srt(path: str) -> list[Caption]:
    captions: list[Caption] = []
    with open(path, encoding="utf-8") as handle:
        index_seen = False
        start: str | None = None
        end: str | None = None
        payload: list[str] = []
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                if start and end:
                    captions.append(Caption(start=start, end=end, text="\n".join(payload)))
                index_seen = False
                start = end = None
                payload = []
                continue
            if not index_seen and line.isdigit():
                index_seen = True
                continue
            if "-->" in line:
                start, end = [part.strip() for part in line.split("-->", 1)]
                start = start.replace(",", ".")
                end = end.replace(",", ".")
                continue
            payload.append(line)
        if start and end:
            captions.append(Caption(start=start, end=end, text="\n".join(payload)))
    return captions


__all__ = ["Caption", "read", "from_srt"]
