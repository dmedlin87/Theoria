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
from dataclasses import asdict, dataclass, field
from importlib.util import module_from_spec, spec_from_file_location
from itertools import count
from pathlib import Path
from typing import Any, Iterable, Sequence

import pythonbible as pb


class _FallbackFaker:
    """Lightweight stand-in mirroring the local ``faker`` test stub."""

    _WORD_BANK = [
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
    ]

    def __init__(self) -> None:
        self._random = random.Random()

    def seed_instance(self, seed: int) -> None:
        self._random.seed(seed)

    def _words(self, nb: int) -> list[str]:
        return [self._random.choice(self._WORD_BANK) for _ in range(nb)]

    def words(self, nb: int = 3) -> list[str]:
        return self._words(max(nb, 0))

    def sentence(self, nb_words: int = 6) -> str:
        words = self._words(max(nb_words, 1))
        return (" ".join(words)).capitalize() + "."

    def sentences(self, nb: int = 3) -> list[str]:
        return [self.sentence() for _ in range(max(nb, 0))]

    def paragraphs(self, nb: int = 3) -> list[str]:
        return [" ".join(self.sentences(nb=3)) for _ in range(max(nb, 0))]


def _resolve_faker() -> type[_FallbackFaker]:
    """Return the deterministic Faker stub even if the real package is present."""

    try:  # pragma: no cover - exercised indirectly by tests
        import faker as faker_module  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover - thin local envs
        faker_module = None  # type: ignore[assignment]

    if faker_module is not None and hasattr(faker_module, "_WORDS"):
        return getattr(faker_module, "Faker")  # type: ignore[return-value]

    stub_path = Path(__file__).resolve().parents[2] / "faker" / "__init__.py"
    if stub_path.exists():
        spec = spec_from_file_location("_theoria_faker_stub", stub_path)
        if spec and spec.loader:  # pragma: no branch - loader present in tests
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            faker_cls = getattr(module, "Faker", None)
            if faker_cls is not None:
                return faker_cls  # type: ignore[return-value]

    if faker_module is not None and hasattr(faker_module, "Faker"):
        return faker_module.Faker  # type: ignore[attr-defined, return-value]

    return _FallbackFaker


Faker = _resolve_faker()

from theo.domain.research.osis import format_osis, osis_to_readable

try:  # pragma: no cover - exercised in lightweight environments
    from theo.services.api.app.ai.rag.models import RAGAnswer, RAGCitation
except Exception:  # pragma: no cover - allows running without pydantic
    @dataclass(frozen=True)
    class RAGCitation:  # type: ignore[override]
        """Fallback citation model used when Pydantic models are unavailable."""

        index: int
        osis: str
        anchor: str
        passage_id: str
        document_id: str
        document_title: str | None = None
        snippet: str = ""
        source_url: str | None = None
        raw_snippet: str | None = None

        def model_dump(self, mode: str | None = None) -> dict[str, Any]:
            """Provide a Pydantic-compatible serialisation hook."""

            data = {
                "index": self.index,
                "osis": self.osis,
                "anchor": self.anchor,
                "passage_id": self.passage_id,
                "document_id": self.document_id,
                "document_title": self.document_title,
                "snippet": self.snippet,
                "source_url": self.source_url,
            }

            # ``raw_snippet`` is marked with ``Field(exclude=True)`` on the
            # Pydantic model so it never appears in serialised output. Mirror
            # that behaviour to avoid fixture mismatches when the fallback is
            # used in lightweight environments.
            return data

    @dataclass
    class RAGAnswer:  # type: ignore[override]
        """Fallback answer model mirroring the Pydantic interface."""

        summary: str
        citations: list[RAGCitation]
        model_name: str | None = None
        model_output: str | None = None
        guardrail_profile: dict[str, str] | None = None
        fallacy_warnings: list[Any] = field(default_factory=list)
        critique: Any = None
        revision: Any = None
        reasoning_trace: Any = None

        def model_dump(self, mode: str | None = None) -> dict[str, Any]:
            """Mirror ``BaseModel.model_dump`` for guardrail helpers."""

            return {
                "summary": self.summary,
                "citations": [
                    citation.model_dump(mode=mode)
                    if hasattr(citation, "model_dump")
                    else asdict(citation)
                    for citation in self.citations
                ],
                "model_name": self.model_name,
                "model_output": self.model_output,
                "guardrail_profile": self.guardrail_profile,
                "fallacy_warnings": self.fallacy_warnings,
                "critique": self.critique,
                "revision": self.revision,
                "reasoning_trace": self.reasoning_trace,
            }

def _canonical_books() -> tuple[pb.Book, ...]:
    """Return the canonical set of books supported by the stub and real package."""

    books = tuple(pb.Book)
    revelation = getattr(pb.Book, "REVELATION", None)
    if revelation is None:
        return books

    revelation_value = getattr(revelation, "value", None)
    if isinstance(revelation_value, int):
        result: list[pb.Book] = []
        for book in books:
            value = getattr(book, "value", None)
            if isinstance(value, int) and value <= revelation_value:
                result.append(book)
        if result:
            return tuple(result)

    try:
        end_index = books.index(revelation)
    except ValueError:
        return books

    return books[: end_index + 1]


CANONICAL_BOOKS: tuple[pb.Book, ...] = _canonical_books()

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
