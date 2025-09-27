"""Ingestion helpers exposed for external callers."""

from .tei_pipeline import (
    HTRClientProtocol,
    HTRResult,
    generate_tei_markup,
    ingest_pilot_corpus,
)

__all__ = [
    "HTRClientProtocol",
    "HTRResult",
    "generate_tei_markup",
    "ingest_pilot_corpus",
]
