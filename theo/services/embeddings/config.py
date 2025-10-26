"""Configuration and instrumentation helpers for embedding rebuild workflows."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Callable, Protocol


@dataclass(slots=True)
class ResourceSnapshot:
    """Lightweight capture of host resource indicators."""

    load_avg_1m: float | None = None
    memory_available: int | None = None


class ResourceProbe(Protocol):
    """Protocol describing a callable that returns resource measurements."""

    def __call__(self) -> ResourceSnapshot:  # pragma: no cover - structural typing helper
        ...


def _try_get_load_average() -> float | None:
    """Return the one minute load average when supported by the platform."""

    try:
        return os.getloadavg()[0]
    except (AttributeError, OSError):  # pragma: no cover - platform specific
        return None


def _try_get_available_memory() -> int | None:
    """Return the available system memory in bytes when psutil is available."""

    try:
        import psutil  # type: ignore
    except Exception:  # pragma: no cover - psutil optional dependency
        return None

    try:
        virtual_memory = psutil.virtual_memory()
    except Exception:  # pragma: no cover - defensive probe
        return None
    return int(getattr(virtual_memory, "available", None) or 0)


def default_resource_probe() -> ResourceSnapshot:
    """Best-effort probe for host load and free memory."""

    return ResourceSnapshot(
        load_avg_1m=_try_get_load_average(),
        memory_available=_try_get_available_memory(),
    )


@dataclass(slots=True)
class EmbeddingRebuildConfig:
    """Runtime configuration for adaptive embedding rebuilds."""

    initial_batch_size: int = 128
    min_batch_size: int = 32
    max_batch_size: int = 256
    commit_cadence: int = 4
    yield_buffer_multiplier: float = 2.0
    max_yield_size: int = 1024
    target_batch_duration: float = 3.5
    increase_threshold: float = 0.6
    decrease_threshold: float = 1.4
    growth_factor: float = 1.4
    shrink_factor: float = 0.65
    high_load_threshold: float = 3.0
    low_memory_threshold_bytes: int | None = 512 * 1024 * 1024
    resource_probe: ResourceProbe = field(default=default_resource_probe, repr=False)

    @classmethod
    def for_mode(cls, *, fast: bool) -> "EmbeddingRebuildConfig":
        """Return configuration tuned for either fast or thorough rebuilds."""

        if fast:
            return cls(
                initial_batch_size=64,
                min_batch_size=24,
                max_batch_size=160,
                commit_cadence=2,
                yield_buffer_multiplier=1.5,
                max_yield_size=512,
                target_batch_duration=2.0,
            )
        return cls()

    def compute_yield_size(self, batch_size: int) -> int:
        """Return the number of rows to request from the database for each fetch."""

        multiplier = max(self.yield_buffer_multiplier, 1.0)
        scaled = int(math.ceil(batch_size * multiplier))
        scaled = max(batch_size, scaled)
        return min(scaled, self.max_yield_size)

    def adjust_batch_size(
        self, *, batch_size: int, duration: float, resource_snapshot: ResourceSnapshot
    ) -> int:
        """Return a new batch size based on timing and host resource data."""

        updated_size = batch_size

        # Shrink aggressively when the host is under pressure.
        if (
            resource_snapshot.load_avg_1m is not None
            and resource_snapshot.load_avg_1m > self.high_load_threshold
        ) or (
            self.low_memory_threshold_bytes is not None
            and resource_snapshot.memory_available is not None
            and resource_snapshot.memory_available < self.low_memory_threshold_bytes
        ):
            updated_size = max(self.min_batch_size, int(batch_size * self.shrink_factor))
            return updated_size

        if duration <= 0:
            return updated_size

        duration_ratio = duration / self.target_batch_duration
        if (
            duration_ratio < self.increase_threshold
            and batch_size < self.max_batch_size
        ):
            updated_size = min(
                self.max_batch_size,
                max(batch_size + 1, int(math.ceil(batch_size * self.growth_factor))),
            )
        elif (
            duration_ratio > self.decrease_threshold
            and batch_size > self.min_batch_size
        ):
            updated_size = max(
                self.min_batch_size,
                int(max(self.min_batch_size, batch_size * self.shrink_factor)),
            )
        return updated_size

    def to_metadata(self) -> dict[str, object]:
        """Return a JSON serialisable view of the adaptive tuning parameters."""

        return {
            "initial_batch_size": self.initial_batch_size,
            "min_batch_size": self.min_batch_size,
            "max_batch_size": self.max_batch_size,
            "commit_cadence": self.commit_cadence,
            "yield_buffer_multiplier": self.yield_buffer_multiplier,
            "max_yield_size": self.max_yield_size,
            "target_batch_duration": self.target_batch_duration,
            "increase_threshold": self.increase_threshold,
            "decrease_threshold": self.decrease_threshold,
            "growth_factor": self.growth_factor,
            "shrink_factor": self.shrink_factor,
            "high_load_threshold": self.high_load_threshold,
            "low_memory_threshold_bytes": self.low_memory_threshold_bytes,
        }


@dataclass(slots=True)
class EmbeddingRebuildInstrumentation:
    """Aggregates timing samples to track rebuild throughput and commits."""

    batches: int = 0
    commits: int = 0
    total_vectors: int = 0
    total_duration: float = 0.0
    throughput_samples: list[float] = field(default_factory=list)
    load_samples: list[float] = field(default_factory=list)
    memory_samples: list[int] = field(default_factory=list)

    def record_batch(
        self,
        *,
        size: int,
        duration: float,
        resource_snapshot: ResourceSnapshot,
    ) -> None:
        """Record metrics for an embedding batch."""

        self.batches += 1
        self.total_vectors += size
        self.total_duration += duration
        if duration > 0:
            self.throughput_samples.append(size / duration)
        if resource_snapshot.load_avg_1m is not None:
            self.load_samples.append(resource_snapshot.load_avg_1m)
        if resource_snapshot.memory_available is not None:
            self.memory_samples.append(resource_snapshot.memory_available)

    def record_commit(self) -> None:
        """Increment the commit counter."""

        self.commits += 1

    def summary(self) -> dict[str, object]:
        """Return aggregate statistics describing the rebuild throughput."""

        avg_throughput = (
            mean(self.throughput_samples) if self.throughput_samples else None
        )
        peak_throughput = (
            max(self.throughput_samples) if self.throughput_samples else None
        )
        slowest_throughput = (
            min(self.throughput_samples) if self.throughput_samples else None
        )
        avg_load = mean(self.load_samples) if self.load_samples else None
        min_memory = min(self.memory_samples) if self.memory_samples else None

        return {
            "batches": self.batches,
            "commits": self.commits,
            "total_vectors": self.total_vectors,
            "total_duration_seconds": self.total_duration,
            "average_throughput_vectors_per_second": avg_throughput,
            "peak_throughput_vectors_per_second": peak_throughput,
            "slowest_throughput_vectors_per_second": slowest_throughput,
            "average_load_1m": avg_load,
            "minimum_available_memory_bytes": min_memory,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def emit(self, *, echo: Callable[[str], object]) -> None:
        """Write a concise throughput summary using the provided echo callable."""

        if not self.batches:
            echo("No batches were processed; skipping instrumentation summary.")
            return

        stats = self.summary()
        throughput = stats["average_throughput_vectors_per_second"]
        throughput_display = f"{throughput:.2f}" if throughput is not None else "n/a"
        echo(
            "Instrumentation: "
            f"{self.batches} batch(es), {self.commits} commit(s), "
            f"avg throughput {throughput_display} vectors/s."
        )

    def dump(self, path: Path) -> None:
        """Persist the collected statistics to a JSON file."""

        payload = self.summary()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

