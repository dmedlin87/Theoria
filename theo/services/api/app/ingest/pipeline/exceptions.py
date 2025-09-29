"""Exceptions for the ingestion pipeline."""


class UnsupportedSourceError(ValueError):
    """Raised when the pipeline cannot parse an input file or URL."""


__all__ = ["UnsupportedSourceError"]
