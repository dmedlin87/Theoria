"""Morphology lookup helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .datasets import morphology_dataset


@dataclass(slots=True)
class MorphToken:
    osis: str
    surface: str
    lemma: str | None = None
    morph: str | None = None
    gloss: str | None = None
    position: int | None = None


def fetch_morphology(osis: str) -> list[MorphToken]:
    """Return token-level morphology for a verse."""

    entries = morphology_dataset().get(osis, [])
    return [
        MorphToken(
            osis=osis,
            surface=entry["surface"],
            lemma=entry.get("lemma"),
            morph=entry.get("morph"),
            gloss=entry.get("gloss"),
            position=entry.get("position"),
        )
        for entry in entries
    ]
