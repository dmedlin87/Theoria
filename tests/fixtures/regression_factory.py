"""Factories for deterministic regression datasets used in CI.

The helpers in this module centralise the construction of realistic
scripture content that mirrors what our RAG pipelines ingest. Each
factory is seeded to ensure that updates to the golden files are
repeatable. Tests can import :class:`RegressionDataFactory` to generate
scripture passages, documents, and model artefacts without hard-coding
literal strings in multiple places.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass
from itertools import count
from typing import Iterable, Sequence

import pythonbible as pb

try:  # pragma: no cover - optional dependency for richer fake text
    from faker import Faker  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - executed when Faker missing
    class Faker:  # type: ignore[override]
        """Minimal stub mirroring the parts of :class:`faker.Faker` that we use."""

        def __init__(self) -> None:
            self._random = random.Random()

        def seed_instance(self, seed: int) -> None:
            self._random.seed(seed)

        def _word(self) -> str:
            length = self._random.randint(3, 8)
            return "".join(self._random.choice(string.ascii_lowercase) for _ in range(length))

        def sentence(self, nb_words: int = 5) -> str:
            words = [self._word() for _ in range(nb_words)]
            sentence = " ".join(words).capitalize()
            return f"{sentence}."

        def sentences(self, nb: int = 3) -> list[str]:
            return [self.sentence() for _ in range(nb)]

from theo.domain.research.osis import format_osis, osis_to_readable
from theo.services.api.app.ai.rag.models import RAGAnswer, RAGCitation

CANONICAL_BOOKS: tuple[pb.Book, ...] = tuple(
    book for book in pb.Book if book.value <= pb.Book.REVELATION.value
)

__all__ = ["DocumentRecord", "PassageRecord", "RegressionDataFactory"]


@dataclass(frozen=True)
class DocumentRecord:
    """Synthetic document metadata suitable for RAG regression tests."""

    id: str
    title: str
    summary: str
    url: str


@dataclass(frozen=True)
class PassageRecord:
    """Synthetic scripture passage metadata."""

    id: str
    osis: str
    anchor: str
    snippet: str
    document: DocumentRecord


class RegressionDataFactory:
    """Build deterministic scripture artefacts for regression tests.

    The factory is intentionally stateful: each call advances the
    underlying Faker and ``random.Random`` instances so that multiple
    tests using the same seed yield stable sequences of documents and
    passages. Re-instantiating the factory resets the sequence to the
    beginning, which keeps per-test fixtures isolated and reproducible.
    """

    def __init__(self, seed: int = 2025) -> None:
        self._seed = seed
        self._faker = Faker()
        self._faker.seed_instance(seed)
        self._random = random.Random(seed)
        self._doc_ids = count(1)
        self._passage_ids = count(1)
        self._citation_ids = count(1)

    def reseed(self, seed: int | None = None) -> None:
        """Reset the internal randomness to a given seed (defaults to init)."""

        value = self._seed if seed is None else seed
        self._seed = value
        self._faker.seed_instance(value)
        self._random.seed(value)
        self._doc_ids = count(1)
        self._passage_ids = count(1)
        self._citation_ids = count(1)

    def document(self) -> DocumentRecord:
        """Create a synthetic document with deterministic metadata."""

        index = next(self._doc_ids)
        doc_id = f"doc-{index}"
        title = self._faker.sentence(nb_words=5).rstrip(".")
        summary = " ".join(self._faker.sentences(nb=2))
        url = f"/doc/{doc_id}"
        return DocumentRecord(id=doc_id, title=title, summary=summary, url=url)

    def _normalized_reference(self, max_span: int = 3) -> pb.NormalizedReference:
        """Generate a ``NormalizedReference`` within a single chapter."""

        book = self._random.choice(CANONICAL_BOOKS)
        chapter_count = pb.get_number_of_chapters(book)
        if chapter_count == 0:  # pragma: no cover - defensive guard
            return pb.NormalizedReference(book, 1, 1, 1, 1)

        chapter = self._random.randint(1, chapter_count)
        verse_count = pb.get_number_of_verses(book, chapter)
        start_verse = self._random.randint(1, verse_count)
        max_length = min(max_span, verse_count - start_verse + 1)
        span = self._random.randint(1, max_length)
        end_verse = start_verse + span - 1
        return pb.NormalizedReference(
            book=book,
            start_chapter=chapter,
            start_verse=start_verse,
            end_chapter=chapter,
            end_verse=end_verse,
        )

    def passage(self, document: DocumentRecord | None = None) -> PassageRecord:
        """Create a passage that references scripture text via pythonbible."""

        doc = document or self.document()
        reference = self._normalized_reference()
        osis_value = format_osis(reference)
        anchor = osis_to_readable(osis_value)
        verse_ids = list(pb.convert_reference_to_verse_ids(reference))
        verse_texts: list[str] = []
        for verse_id in verse_ids:
            try:
                verse_texts.append(pb.get_verse_text(verse_id))
            except pb.VersionMissingVerseError:
                verse_texts.append(
                    pb.get_verse_text(verse_id, version=pb.Version.KING_JAMES)
                )
        snippet = " ".join(" ".join(verse_texts).split())
        passage_id = f"passage-{next(self._passage_ids)}"
        return PassageRecord(
            id=passage_id,
            osis=osis_value,
            anchor=anchor,
            snippet=snippet,
            document=doc,
        )

    def rag_citation(
        self, *, index: int | None = None, passage: PassageRecord | None = None
    ) -> RAGCitation:
        """Construct a :class:`RAGCitation` tied to a generated passage."""

        passage_record = passage or self.passage()
        citation_index = index if index is not None else next(self._citation_ids)
        return RAGCitation(
            index=citation_index,
            osis=passage_record.osis,
            anchor=passage_record.anchor,
            passage_id=passage_record.id,
            document_id=passage_record.document.id,
            document_title=passage_record.document.title,
            snippet=passage_record.snippet,
            source_url=f"{passage_record.document.url}#{passage_record.id}",
        )

    def rag_citations(self, count: int) -> list[RAGCitation]:
        """Produce ``count`` sequential citations."""

        return [self.rag_citation(index=i + 1) for i in range(count)]

    def rag_answer(
        self,
        *,
        citations: Sequence[RAGCitation] | None = None,
        model_name: str | None = None,
    ) -> RAGAnswer:
        """Create a :class:`RAGAnswer` seeded with deterministic prose."""

        citation_list = list(citations) if citations is not None else self.rag_citations(2)
        summary = " ".join(self._faker.sentences(nb=2))
        detail = self._faker.paragraphs(nb=1)[0]
        model = model_name or "theo-regression-gpt"
        sources = ", ".join(
            f"[{citation.index}] {citation.osis} ({citation.anchor})" for citation in citation_list
        )
        model_output = f"{detail}\n\nSources: {sources}"
        return RAGAnswer(
            summary=summary,
            citations=citation_list,
            model_name=model,
            model_output=model_output,
        )

    def conversation_highlights(self, count: int = 2) -> list[str]:
        """Return deterministic conversational snippets for prompt context."""

        return [" ".join(self._faker.words(nb=8)).capitalize() + "." for _ in range(count)]

    def question(self) -> str:
        """Generate a deterministic question for prompt builders."""

        return self._faker.sentence(nb_words=6).rstrip(".") + "?"

    def golden_payload(self, citations: Iterable[RAGCitation]) -> list[dict[str, str | int]]:
        """Serialize citations into a JSON-friendly format for golden files."""

        payload: list[dict[str, str | int]] = []
        for citation in citations:
            payload.append(
                {
                    "index": citation.index,
                    "osis": citation.osis,
                    "anchor": citation.anchor,
                    "passage_id": citation.passage_id,
                    "document_id": citation.document_id,
                    "document_title": citation.document_title,
                    "snippet": citation.snippet,
                    "source_url": citation.source_url,
                }
            )
        return payload
