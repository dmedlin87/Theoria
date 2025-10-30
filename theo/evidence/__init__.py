"""Evidence toolkit for working with theological research corpora."""

from __future__ import annotations

from .citations import is_valid_csl_citekey
from .cli import cli
from .dossier import EvidenceDossier
from .indexer import EvidenceIndexer
from .models import EvidenceCitation, EvidenceCollection, EvidenceRecord
from .normalization import normalize_many, normalize_reference
from .promoter import EvidencePromoter
from .validator import EvidenceValidator, validate

__all__ = [
    "EvidenceCitation",
    "EvidenceCollection",
    "EvidenceRecord",
    "EvidenceDossier",
    "EvidenceIndexer",
    "EvidencePromoter",
    "EvidenceValidator",
    "cli",
    "is_valid_csl_citekey",
    "normalize_many",
    "normalize_reference",
    "validate",
]
