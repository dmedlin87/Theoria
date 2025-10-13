"""Compatibility shim forwarding to :mod:`theo.domain.research.datasets`."""
from __future__ import annotations

from warnings import warn

from ..compat.research.datasets import (
    crossref_dataset,
    dss_links_dataset,
    fallacy_dataset,
    historicity_dataset,
    morphology_dataset,
    report_templates_dataset,
    scripture_dataset,
    variants_dataset,
)

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
