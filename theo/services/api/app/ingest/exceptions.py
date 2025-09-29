"""Custom exceptions for ingestion flows."""


class UnsupportedSourceError(ValueError):
    """Raised when the ingestion pipeline cannot process a source."""

