"""Compatibility re-exports for research datasets."""
from __future__ import annotations

from warnings import warn

from theo.domain.research.datasets import *  # noqa: F401,F403

warn(
    "Importing from 'theo.services.api.app.research.datasets' is deprecated; "
    "use 'theo.domain.research.datasets' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "crossref_dataset",
    "dss_links_dataset",
    "fallacy_dataset",
    "historicity_dataset",
    "morphology_dataset",
    "report_templates_dataset",
    "scripture_dataset",
    "variants_dataset",
]
