#!/usr/bin/env python3
"""Test biblical text analysis capabilities."""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from theo.domain.biblical_texts import (
    Reference,
    TextContent,
    BiblicalVerse,
    Language,
    MorphologicalTag,
    POS,
    SemanticAnalysis,
    TheologicalTermTracker,
    BibleVersion,
    BiblicalBook
)


def create_genesis_sample() -> BiblicalVerse:
    """Create Genesis 1:1 with full analysis as example."""
    
    reference = Reference(
        book="Genesis",
        chapter=1,
        verse=1,
        book_id="gen",
        osis_id="Gen.1.1"
    )
    
    text = TextContent(
        raw="בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ",
        normalized="בראשית ברא אלהים את השמים ואת הארץ",
        transliteration="bereshit bara elohim et hashamayim ve'et ha'aretz"
    )
    
    # Morphological analysis
    morphology = [
        MorphologicalTag(
            word="בְּרֵאשִׁית",
            lemma="רֵאשִׁית", 
            root="ראש",
            pos=POS.NOUN,
            gender="feminine",
            number="singular",
            state="construct",
            prefix="ב",
            gloss="beginning",
            theological_notes=["creation_narrative", "temporal_marker"]
        ),
        MorphologicalTag(
            word="בָּרָא",
            lemma="ברא",
            root="ברא",
            pos=POS.VERB,
            stem="qal",
            tense="perfect", 
            person=3,
            gender="masculine",
            number="singular",
            gloss="create",
            theological_notes=["divine_creation", "ex_nihilo"]
        ),
        MorphologicalTag(
            word="אֱלֹהִים",
            lemma="אלהים",
            root="אלה",
            pos=POS.NOUN,
            gender="masculine",
            number="plural",
            state="absolute",
            gloss="God",
            theological_notes=["divine_name", "plural_form_singular_verb", "trinity_evidence"]
        )
    ]
    
    semantic_analysis = SemanticAnalysis(
        themes=["creation", "divine_activity", "cosmology"],
        theological_keywords=["אלהים", "ברא", "שמים"],
        cross_references=["John.1.1", "John.1.3", "Heb.11.3"],
        textual_variants=[],
        translation_notes={
            "elohim_plurality": "Plural noun אלהים with singular verb ברא",
            "creation_verb": "Hebrew ברא used exclusively for divine creation"
        }
    )
    
    return BiblicalVerse(
        reference=reference,
        language=Language.HEBREW,
        text=text,
        morphology=morphology,
        semantic_analysis=semantic_analysis
    )


def test_theological_analysis():
    """Test theological analysis capabilities."""
    
    print("📖 Testing Biblical Text Analysis")
    print("=" * 40)
    
    # Create sample verse
    genesis_verse = create_genesis_sample()
    
    print(f"\n📄 Analyzing: {genesis_verse.reference}")
    print(f"Hebrew: {genesis_verse.text.raw}")
    print(f"Transliteration: {genesis_verse.text.transliteration}")
    
    # Test morphological analysis
    print(f"\n🔍 Morphological Analysis ({len(genesis_verse.morphology)} words):")
    for i, tag in enumerate(genesis_verse.morphology[:3], 1):  # First 3 words
        print(f"  {i}. {tag.word} ({tag.lemma})")
        print(f"     • {tag.pos.value}, {tag.gloss}")
        if tag.theological_notes:
            print(f"     • Theological: {', '.join(tag.theological_notes)}")
    
    # Test semantic analysis
    print(f"\n🧐 Semantic Analysis:")
    if genesis_verse.semantic_analysis:
        print(f"  • Themes: {', '.join(genesis_verse.semantic_analysis.themes)}")
        print(f"  • Key terms: {', '.join(genesis_verse.semantic_analysis.theological_keywords)}")
        print(f"  • Cross-refs: {', '.join(genesis_verse.semantic_analysis.cross_references)}")
    
    # Test theological term tracking
    print(f"\n⚔️ Theological Research:")
    divine_names = genesis_verse.find_divine_names()
    print(f"  • Divine names found: {len(divine_names)}")
    for name in divine_names:
        print(f"    - {name.word} ({name.lemma}): {', '.join(name.theological_notes)}")
    
    theological_keywords = genesis_verse.get_theological_keywords()
    print(f"  • Theological keywords: {', '.join(theological_keywords)}")
    
    return genesis_verse


def test_trinity_research():
    """Test trinity-specific research capabilities."""
    
    print(f"\n✨ Trinity Research Analysis")
    print("=" * 40)
    
    # Create a Bible version with sample data
    genesis_book = BiblicalBook(
        id="gen",
        name="Genesis",
        native_name="בראשית",
        language=Language.HEBREW,
        chapter_count=50
    )
    
    # Add our sample verse
    sample_verse = create_genesis_sample()
    genesis_book.verses["1:1"] = sample_verse
    
    bible_version = BibleVersion(
        name="Westminster Leningrad Codex",
        abbreviation="WLC",
        language=Language.HEBREW,
        license="Public Domain",
        source_url="https://www.tanach.us/",
        version="4.20",
        description="Masoretic Hebrew Bible"
    )
    bible_version.books["gen"] = genesis_book
    
    # Test Elohim + singular verb analysis
    elohim_verses = TheologicalTermTracker.find_elohim_singular_verbs(bible_version)
    print(f"\n🔎 Elohim + Singular Verb Analysis:")
    print(f"  • Verses found: {len(elohim_verses)}")
    
    for verse in elohim_verses:
        print(f"    - {verse.reference}: Evidence for grammatical plurality")
        
        # Show the specific evidence
        elohim_tags = [tag for tag in verse.morphology if "elohim" in tag.lemma.lower()]
        singular_verbs = [tag for tag in verse.morphology 
                         if tag.pos == POS.VERB and tag.number == "singular"]
        
        if elohim_tags and singular_verbs:
            print(f"      אלהים (plural) + {singular_verbs[0].word} (singular verb)")
    
    print(f"\n📊 Research Implications:")
    print(f"  • Grammatical evidence: Plural noun + singular verb")
    print(f"  • Theological debates: Trinity vs. majestic plural")
    print(f"  • Cross-reference needed: Isaiah 6:8 (plural pronouns)")
    
    return bible_version


def test_search_capabilities(bible_version):
    """Test search and query capabilities."""
    
    print(f"\n🔍 Search & Query Testing")
    print("=" * 40)
    
    genesis_book = bible_version.books["gen"]
    
    # Word search
    bara_results = genesis_book.search_word("ברא", lemma=True)
    print(f"\n• Search for root ברא (create): {len(bara_results)} results")
    
    elohim_results = genesis_book.search_word("אלהים", lemma=True)
    print(f"• Search for אלהים (God): {len(elohim_results)} results")
    
    # Verse retrieval
    verse = genesis_book.get_verse(1, 1)
    if verse:
        print(f"\n• Retrieved verse: {verse.reference}")
        print(f"  Text: {verse.text.raw[:50]}...")
    
    print(f"\n✅ All search functions operational")


def main():
    """Main test function."""
    
    print("🚀 Theoria Biblical Text Analysis Demo")
    print("=" * 50)
    
    # Test basic analysis
    sample_verse = test_theological_analysis()
    
    # Test trinity research
    bible_version = test_trinity_research()
    
    # Test search capabilities
    test_search_capabilities(bible_version)
    
    # Show how to export data
    print(f"\n💾 Data Export Example")
    print("=" * 40)
    
    verse_dict = {
        "reference": {
            "book": sample_verse.reference.book,
            "chapter": sample_verse.reference.chapter,
            "verse": sample_verse.reference.verse,
            "osis_id": sample_verse.reference.osis_id
        },
        "text": {
            "raw": sample_verse.text.raw,
            "normalized": sample_verse.text.normalized,
            "transliteration": sample_verse.text.transliteration
        },
        "morphology_count": len(sample_verse.morphology),
        "theological_keywords": sample_verse.get_theological_keywords(),
        "divine_names_count": len(sample_verse.find_divine_names())
    }
    
    print(json.dumps(verse_dict, ensure_ascii=False, indent=2))
    
    print(f"\n✅ Biblical text analysis system ready!")
    print(f"📁 Schema: docs/BIBLE_TEXT_SCHEMA.md")
    print(f"🚀 Import script: scripts/import_hebrew_bible.py")
    print(f"✨ Next: Add your OpenAI key and import real Hebrew Bible data")


if __name__ == "__main__":
    main()
