"""Lightweight subset of the :mod:`faker` package used in tests.

This stub implements only the behaviours exercised by the regression
fixtures.  It provides a deterministic pseudo-random text generator with
an interface compatible with the real ``faker.Faker`` class for the
small subset of methods that the test-suite relies upon.

The implementation intentionally keeps the surface area narrow so that
we avoid taking an additional third-party dependency in CI while still
producing human-readable placeholder text.
"""

from __future__ import annotations

import random
from typing import List

__all__ = ["Faker"]


_WORDS: tuple[str, ...] = (
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "india",
    "juliet",
    "kilo",
    "lima",
    "mike",
    "november",
    "oscar",
    "papa",
    "quebec",
    "romeo",
    "sierra",
    "tango",
    "uniform",
    "victor",
    "whiskey",
    "xray",
    "yankee",
    "zulu",
)


class Faker:
    """Minimal stand-in for :class:`faker.Faker` used in tests.

    Only the methods exercised in the suite are implemented.  Additional
    functionality should be added on demand to keep the stub focused and
    maintainable.
    """

    def __init__(self) -> None:
        self._random = random.Random()

    def seed_instance(self, seed: int) -> None:
        """Seed the underlying pseudo-random generator."""

        self._random.seed(seed)

    # -- helpers -----------------------------------------------------------------
    def _word(self) -> str:
        return self._random.choice(_WORDS)

    def _words(self, count: int) -> List[str]:
        return [self._word() for _ in range(count)]

    def words(self, nb: int = 3) -> List[str]:
        """Return ``nb`` pseudo-random words."""

        return self._words(nb)

    def sentence(self, nb_words: int = 6) -> str:
        """Return a capitalised sentence terminating with a period."""

        words = self._words(max(nb_words, 1))
        sentence = " ".join(words)
        return f"{sentence.capitalize()}."

    def sentences(self, nb: int = 3) -> List[str]:
        """Return a list of ``nb`` generated sentences."""

        return [self.sentence() for _ in range(max(nb, 0))]

    def paragraphs(self, nb: int = 3) -> List[str]:
        """Return a list of paragraphs comprised of generated sentences."""

        return [" ".join(self.sentences(nb=3)) for _ in range(max(nb, 0))]

    def _sentence_without_period(self, nb_words: int) -> str:
        return self.sentence(nb_words=nb_words).rstrip(".")

    # -- compatibility helpers used in tests -------------------------------------
    def paragraph(self) -> str:
        return self.paragraphs(nb=1)[0]

    def text(self) -> str:
        return " ".join(self.sentences(nb=3))

