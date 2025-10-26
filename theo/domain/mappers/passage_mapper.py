"""Mapping utilities between ORM passages and :mod:`biblical_texts` domain models."""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Mapping

from theo.domain.biblical_texts import (
    AIAnalysis,
    BiblicalVerse,
    HebrewStem,
    GreekTense,
    Language,
    ManuscriptData,
    MorphologicalTag,
    POS,
    Reference,
    SemanticAnalysis,
    TextContent,
)

if TYPE_CHECKING:  # pragma: no cover - imported only for typing hints
    from theo.adapters.persistence.models import Passage  # noqa: F401
else:  # pragma: no cover - runtime duck typing
    Passage = Any  # type: ignore[misc, assignment]


class PassageMapper:
    """Translate between ORM :class:`Passage` rows and :class:`BiblicalVerse` aggregates."""

    META_KEY = "biblical_text"
    _DIRECT_META_KEYS = {
        "reference",
        "language",
        "text",
        "morphology",
        "semantic_analysis",
        "manuscript_data",
        "ai_analysis",
    }

    def to_domain(self, passage: Passage) -> BiblicalVerse:
        """Convert an ORM ``Passage`` into a :class:`BiblicalVerse` value object."""

        meta: Mapping[str, Any] | None = getattr(passage, "meta", None)
        payload, _ = self._extract_payload(meta)

        reference = self._build_reference(payload, getattr(passage, "osis_ref", None))
        text = self._build_text_content(payload, passage)
        language = self._coerce_language(payload.get("language"))
        morphology = self._build_morphology(payload.get("morphology"))
        semantic_analysis = self._build_semantic(payload.get("semantic_analysis"))
        manuscript_data = self._build_manuscript(payload.get("manuscript_data"))
        ai_analysis = self._build_ai(payload.get("ai_analysis"))

        return BiblicalVerse(
            reference=reference,
            language=language,
            text=text,
            morphology=morphology,
            semantic_analysis=semantic_analysis,
            manuscript_data=manuscript_data,
            ai_analysis=ai_analysis,
        )

    def to_meta_payload(self, verse: BiblicalVerse) -> dict[str, Any]:
        """Render a :class:`BiblicalVerse` into a JSON-serialisable payload."""

        payload: dict[str, Any] = {
            "reference": {
                "book": verse.reference.book,
                "chapter": verse.reference.chapter,
                "verse": verse.reference.verse,
                "book_id": verse.reference.book_id,
                "osis_id": verse.reference.osis_id,
            },
            "language": verse.language.value,
            "text": {
                "raw": verse.text.raw,
                "normalized": verse.text.normalized,
                "transliteration": verse.text.transliteration,
            },
        }

        if verse.morphology:
            payload["morphology"] = [self._morph_tag_to_dict(tag) for tag in verse.morphology]
        if verse.semantic_analysis:
            payload["semantic_analysis"] = asdict(verse.semantic_analysis)
        if verse.manuscript_data:
            payload["manuscript_data"] = asdict(verse.manuscript_data)
        if verse.ai_analysis:
            ai_dict = asdict(verse.ai_analysis)
            generated_at = ai_dict.get("generated_at")
            if isinstance(generated_at, datetime):
                ai_dict["generated_at"] = generated_at.astimezone(UTC).isoformat()
            payload["ai_analysis"] = ai_dict

        return payload

    def merge_meta(self, meta: Mapping[str, Any] | None, verse: BiblicalVerse) -> dict[str, Any]:
        """Merge *meta* with the biblical payload derived from *verse*."""

        merged: dict[str, Any] = dict(meta or {})
        merged[self.META_KEY] = self.to_meta_payload(verse)
        return merged

    def update_orm(self, passage: Passage, verse: BiblicalVerse) -> Passage:
        """Apply a :class:`BiblicalVerse` onto an ORM ``Passage`` record in-place."""

        payload_meta = self.merge_meta(getattr(passage, "meta", None), verse)
        text_value = verse.text.normalized or verse.text.raw or getattr(passage, "text", "")
        setattr(passage, "text", text_value)
        raw_text_value = verse.text.raw or getattr(passage, "raw_text", None)
        setattr(passage, "raw_text", raw_text_value)
        setattr(passage, "meta", payload_meta)
        setattr(passage, "osis_ref", verse.reference.osis_id)
        return passage

    def has_biblical_payload(self, meta: Mapping[str, Any] | None) -> bool:
        """Return ``True`` if *meta* already stores biblical verse information."""

        if not meta:
            return False
        if isinstance(meta.get(self.META_KEY), Mapping):
            return True
        return any(key in meta for key in self._DIRECT_META_KEYS)

    def _extract_payload(self, meta: Mapping[str, Any] | None) -> tuple[dict[str, Any], bool]:
        if not isinstance(meta, Mapping):
            return {}, False
        nested = meta.get(self.META_KEY)
        if isinstance(nested, Mapping):
            return dict(nested), True
        extracted = {key: meta[key] for key in self._DIRECT_META_KEYS if key in meta}
        return extracted, bool(extracted)

    def _build_reference(self, payload: Mapping[str, Any], osis_ref: str | None) -> Reference:
        raw_ref = payload.get("reference") if isinstance(payload.get("reference"), Mapping) else {}
        book = str(raw_ref.get("book") or self._guess_book(osis_ref) or "Unknown")
        chapter = self._coerce_int(raw_ref.get("chapter")) or self._guess_chapter(osis_ref)
        verse = self._coerce_int(raw_ref.get("verse")) or self._guess_verse(osis_ref)
        book_id = str(raw_ref.get("book_id") or self._slugify_book(book))
        osis_id = str(raw_ref.get("osis_id") or osis_ref or f"{book}.{chapter}.{verse}")
        return Reference(book=book, chapter=chapter, verse=verse, book_id=book_id, osis_id=osis_id)

    def _build_text_content(self, payload: Mapping[str, Any], passage: Passage) -> TextContent:
        text_payload = payload.get("text") if isinstance(payload.get("text"), Mapping) else {}
        raw = text_payload.get("raw") or getattr(passage, "raw_text", None) or getattr(passage, "text", "")
        normalized = text_payload.get("normalized") or getattr(passage, "text", None) or raw
        transliteration = text_payload.get("transliteration")
        return TextContent(raw=str(raw or ""), normalized=str(normalized or ""), transliteration=transliteration)

    def _coerce_language(self, value: Any) -> Language:
        if isinstance(value, Language):
            return value
        if isinstance(value, str):
            lowered = value.lower()
            for candidate in Language:
                if candidate.value == lowered or candidate.name.lower() == lowered:
                    return candidate
        return Language.ENGLISH

    def _build_morphology(self, value: Any) -> list[MorphologicalTag]:
        if not isinstance(value, list):
            return []
        tags: list[MorphologicalTag] = []
        for item in value:
            if not isinstance(item, Mapping):
                continue
            pos = self._coerce_enum(item.get("pos"), POS)
            if pos is None:
                continue
            tag = MorphologicalTag(
                word=str(item.get("word") or ""),
                lemma=str(item.get("lemma") or ""),
                root=item.get("root"),
                pos=pos,
                gender=item.get("gender"),
                number=item.get("number"),
                state=item.get("state"),
                stem=self._coerce_enum(item.get("stem"), HebrewStem, allow_strings=True),
                tense=self._coerce_enum(item.get("tense"), GreekTense, allow_strings=True),
                person=self._coerce_int(item.get("person")),
                prefix=item.get("prefix"),
                suffix=item.get("suffix"),
                gloss=str(item.get("gloss") or ""),
                theological_notes=list(item.get("theological_notes") or []),
            )
            tags.append(tag)
        return tags

    def _build_semantic(self, value: Any) -> SemanticAnalysis | None:
        if not isinstance(value, Mapping):
            return None
        return SemanticAnalysis(
            themes=list(value.get("themes") or []),
            theological_keywords=list(value.get("theological_keywords") or []),
            cross_references=list(value.get("cross_references") or []),
            textual_variants=list(value.get("textual_variants") or []),
            translation_notes=dict(value.get("translation_notes") or {}),
        )

    def _build_manuscript(self, value: Any) -> ManuscriptData | None:
        if not isinstance(value, Mapping):
            return None
        return ManuscriptData(
            source=str(value.get("source") or ""),
            variants=list(value.get("variants") or []),
            masoretic_notes=list(value.get("masoretic_notes") or []),
            critical_apparatus=list(value.get("critical_apparatus") or []),
        )

    def _build_ai(self, value: Any) -> AIAnalysis | None:
        if not isinstance(value, Mapping):
            return None
        generated_at = value.get("generated_at")
        if isinstance(generated_at, str):
            generated_at = self._parse_datetime(generated_at)
        elif not isinstance(generated_at, datetime):
            generated_at = None
        confidence = value.get("confidence_scores")
        confidence_scores = dict(confidence) if isinstance(confidence, Mapping) else {}
        model_version = str(value.get("model_version") or "")
        if not generated_at:
            generated_at = datetime.now(tz=UTC)
        return AIAnalysis(
            generated_at=generated_at,
            model_version=model_version,
            confidence_scores=confidence_scores,
        )

    def _morph_tag_to_dict(self, tag: MorphologicalTag) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "word": tag.word,
            "lemma": tag.lemma,
            "root": tag.root,
            "pos": tag.pos.value if isinstance(tag.pos, POS) else tag.pos,
            "gender": tag.gender,
            "number": tag.number,
            "state": tag.state,
            "stem": tag.stem.value if isinstance(tag.stem, HebrewStem) else tag.stem,
            "tense": tag.tense.value if hasattr(tag.tense, "value") else tag.tense,
            "person": tag.person,
            "prefix": tag.prefix,
            "suffix": tag.suffix,
            "gloss": tag.gloss,
            "theological_notes": list(tag.theological_notes),
        }
        return payload

    def _coerce_enum(self, value: Any, enum_cls: Any, *, allow_strings: bool = False) -> Any:
        if isinstance(value, enum_cls):
            return value
        if isinstance(value, str):
            lowered = value.lower()
            for candidate in enum_cls:
                if candidate.value == lowered or candidate.name.lower() == lowered:
                    return candidate
            if allow_strings:
                return value
        return None

    def _coerce_int(self, value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _parse_datetime(self, value: str) -> datetime:
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            return datetime.now(tz=UTC)

    def _guess_book(self, osis: str | None) -> str | None:
        if not osis or "." not in osis:
            return None
        return osis.split(".", 1)[0]

    def _guess_chapter(self, osis: str | None) -> int:
        if not osis:
            return 0
        parts = osis.split(".")
        if len(parts) >= 2:
            return self._coerce_int(parts[1]) or 0
        return 0

    def _guess_verse(self, osis: str | None) -> int:
        if not osis:
            return 0
        parts = osis.split(".")
        if len(parts) >= 3:
            verse_part = parts[2].split("-", 1)[0]
            return self._coerce_int(verse_part) or 0
        return 0

    def _slugify_book(self, book: str) -> str:
        return book.lower().replace(" ", "-")[:8]

