"""Ingestion pipeline orchestration."""

from pathlib import Path


def run_pipeline_for_file(document_id: str, path: Path, frontmatter: dict | None) -> None:
    """Execute the file ingestion pipeline (placeholder)."""


def run_pipeline_for_url(document_id: str, url: str, source_type: str | None) -> None:
    """Execute the URL ingestion pipeline (placeholder)."""
