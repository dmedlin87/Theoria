from theo.domain.biblical_texts import (
    BiblicalVerse,
    Language,
    MorphologicalTag,
    POS,
    Reference,
    SemanticAnalysis,
    TextContent,
)
from theo.adapters.persistence.models import Passage
from theo.domain.mappers import PassageMapper


def test_to_domain_parses_biblical_payload() -> None:
    mapper = PassageMapper()
    passage = Passage()
    passage.id = "p-1"
    passage.document_id = "doc-1"
    passage.text = "בראשית ברא אלהים"
    passage.raw_text = "בְּרֵאשִׁית בָּרָא אֱלֹהִים"
    passage.osis_ref = "Gen.1.1"
    passage.meta = {
        "biblical_text": {
            "reference": {
                "book": "Genesis",
                "chapter": 1,
                "verse": 1,
                "book_id": "gen",
                "osis_id": "Gen.1.1",
            },
            "language": "hebrew",
            "text": {
                "raw": "בְּרֵאשִׁית בָּרָא אֱלֹהִים",
                "normalized": "בראשית ברא אלהים",
                "transliteration": "bereshit bara elohim",
            },
            "morphology": [
                {
                    "word": "בראשית",
                    "lemma": "ראשית",
                    "root": "ראש",
                    "pos": "noun",
                    "gloss": "beginning",
                    "theological_notes": ["creation"],
                }
            ],
            "semantic_analysis": {
                "themes": ["creation"],
                "theological_keywords": ["אלהים"],
                "cross_references": ["John.1.1"],
                "textual_variants": [],
                "translation_notes": {"note": "plural noun with singular verb"},
            },
            "manuscript_data": {
                "source": "WLC",
                "variants": [],
                "masoretic_notes": ["accent"],
                "critical_apparatus": [],
            },
            "ai_analysis": {
                "generated_at": "2024-01-01T00:00:00+00:00",
                "model_version": "gpt-4",
                "confidence_scores": {"morphology": 0.9},
            },
        }
    }

    verse = mapper.to_domain(passage)

    assert verse.reference.osis_id == "Gen.1.1"
    assert verse.language is Language.HEBREW
    assert verse.text.raw == "בְּרֵאשִׁית בָּרָא אֱלֹהִים"
    assert len(verse.morphology) == 1
    assert verse.morphology[0].pos is POS.NOUN
    assert verse.semantic_analysis is not None
    assert verse.semantic_analysis.themes == ["creation"]
    assert verse.manuscript_data is not None
    assert verse.manuscript_data.source == "WLC"
    assert verse.ai_analysis is not None
    assert verse.ai_analysis.model_version == "gpt-4"


def test_update_orm_merges_meta_and_text_fields() -> None:
    mapper = PassageMapper()
    verse = BiblicalVerse(
        reference=Reference("Genesis", 1, 1, "gen", "Gen.1.1"),
        language=Language.HEBREW,
        text=TextContent(
            raw="בְּרֵאשִׁית בָּרָא אֱלֹהִים",
            normalized="בראשית ברא אלהים",
            transliteration="bereshit bara elohim",
        ),
        morphology=[
            MorphologicalTag(
                word="בראשית",
                lemma="ראשית",
                root="ראש",
                pos=POS.NOUN,
                gloss="beginning",
            )
        ],
        semantic_analysis=SemanticAnalysis(
            themes=["creation"],
            theological_keywords=[],
            cross_references=[],
            textual_variants=[],
        ),
    )
    passage = Passage()
    passage.id = "p-merge"
    passage.document_id = "doc-merge"
    passage.text = "old"
    passage.raw_text = "old"
    passage.osis_ref = None
    passage.meta = {"section": "intro"}

    mapper.update_orm(passage, verse)

    assert passage.text == "בראשית ברא אלהים"
    assert passage.raw_text == "בְּרֵאשִׁית בָּרָא אֱלֹהִים"
    assert passage.osis_ref == "Gen.1.1"
    assert passage.meta is not None
    assert passage.meta["section"] == "intro"
    assert "biblical_text" in passage.meta
    biblical_meta = passage.meta["biblical_text"]
    assert biblical_meta["language"] == "hebrew"
    assert biblical_meta["morphology"][0]["word"] == "בראשית"
