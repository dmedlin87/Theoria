"""Domain models for biblical texts with morphological and semantic analysis."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union


class Language(Enum):
    """Supported biblical languages."""
    HEBREW = "hebrew"
    ARAMAIC = "aramaic"
    GREEK = "greek"
    LATIN = "latin"
    ENGLISH = "english"


class POS(Enum):
    """Parts of speech for morphological analysis."""
    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    PRONOUN = "pronoun"
    PREPOSITION = "preposition"
    CONJUNCTION = "conjunction"
    PARTICLE = "particle"
    INTERJECTION = "interjection"


class HebrewStem(Enum):
    """Hebrew verb stems (binyanim)."""
    QAL = "qal"
    NIPHAL = "niphal"
    PIEL = "piel"
    PUAL = "pual"
    HIPHIL = "hiphil"
    HOPHAL = "hophal"
    HITHPAEL = "hithpael"


class GreekTense(Enum):
    """Greek verb tenses."""
    PRESENT = "present"
    IMPERFECT = "imperfect"
    AORIST = "aorist"
    PERFECT = "perfect"
    PLUPERFECT = "pluperfect"
    FUTURE = "future"


@dataclass(frozen=True)
class Reference:
    """Biblical reference identifier."""
    book: str
    chapter: int
    verse: int
    book_id: str
    osis_id: str
    
    def __str__(self) -> str:
        return f"{self.book} {self.chapter}:{self.verse}"


@dataclass(frozen=True)
class TextContent:
    """Raw and normalized text content."""
    raw: str  # Original with vowels, accents, etc.
    normalized: str  # Consonants only or simplified
    transliteration: Optional[str] = None
    

@dataclass(frozen=True)
class MorphologicalTag:
    """Morphological analysis of a single word."""
    word: str
    lemma: str
    root: Optional[str]
    pos: POS
    
    # Nominal features
    gender: Optional[str] = None
    number: Optional[str] = None
    state: Optional[str] = None  # Hebrew: absolute, construct, determined
    
    # Verbal features
    stem: Optional[Union[HebrewStem, str]] = None
    tense: Optional[Union[GreekTense, str]] = None
    person: Optional[int] = None
    
    # Prefixes/suffixes
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    
    # Semantic info
    gloss: str = ""
    theological_notes: List[str] = field(default_factory=list)
    

@dataclass(frozen=True)
class SemanticAnalysis:
    """Semantic and theological analysis of the verse."""
    themes: List[str]
    theological_keywords: List[str]
    cross_references: List[str]
    textual_variants: List[str]
    translation_notes: Dict[str, str] = field(default_factory=dict)
    

@dataclass(frozen=True)
class ManuscriptData:
    """Manuscript and textual criticism data."""
    source: str  # WLC, NA28, etc.
    variants: List[str]
    masoretic_notes: List[str] = field(default_factory=list)
    critical_apparatus: List[str] = field(default_factory=list)
    

@dataclass(frozen=True)
class AIAnalysis:
    """AI-generated analysis metadata."""
    generated_at: datetime
    model_version: str
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    

@dataclass(frozen=True)
class BiblicalVerse:
    """Complete verse with all analysis layers."""
    reference: Reference
    language: Language
    text: TextContent
    morphology: List[MorphologicalTag] = field(default_factory=list)
    semantic_analysis: Optional[SemanticAnalysis] = None
    manuscript_data: Optional[ManuscriptData] = None
    ai_analysis: Optional[AIAnalysis] = None
    
    def get_words(self) -> List[str]:
        """Extract individual words from morphology."""
        return [tag.word for tag in self.morphology]
    
    def get_theological_keywords(self) -> List[str]:
        """Extract theological keywords from morphology and semantics."""
        keywords = []
        
        # From morphological tags
        for tag in self.morphology:
            if tag.theological_notes:
                keywords.append(tag.word)
                
        # From semantic analysis
        if self.semantic_analysis:
            keywords.extend(self.semantic_analysis.theological_keywords)
            
        return list(set(keywords))
    
    def find_divine_names(self) -> List[MorphologicalTag]:
        """Find divine name occurrences in the verse."""
        divine_roots = ["אלה", "יהוה", "אדן", "שדי"]
        return [
            tag for tag in self.morphology 
            if tag.root in divine_roots or "divine_name" in tag.theological_notes
        ]


@dataclass(frozen=True)
class BiblicalBook:
    """A complete biblical book with metadata."""
    id: str
    name: str
    native_name: Optional[str]
    language: Language
    chapter_count: int
    verses: Dict[str, BiblicalVerse] = field(default_factory=dict)  # key: "1:1"
    
    def get_verse(self, chapter: int, verse: int) -> Optional[BiblicalVerse]:
        """Retrieve a specific verse."""
        key = f"{chapter}:{verse}"
        return self.verses.get(key)
    
    def search_word(self, word: str, lemma: bool = False) -> List[BiblicalVerse]:
        """Search for a word or lemma across the book."""
        results = []
        for verse in self.verses.values():
            for tag in verse.morphology:
                search_target = tag.lemma if lemma else tag.word
                if word in search_target:
                    results.append(verse)
                    break
        return results


@dataclass(frozen=True)
class BibleVersion:
    """A complete Bible version with metadata."""
    name: str
    abbreviation: str
    language: Language
    license: str
    source_url: Optional[str]
    version: str
    description: str
    features: List[str] = field(default_factory=list)
    books: Dict[str, BiblicalBook] = field(default_factory=dict)
    
    def get_book(self, book_id: str) -> Optional[BiblicalBook]:
        """Retrieve a book by ID."""
        return self.books.get(book_id)
    
    def get_verse(self, reference: Reference) -> Optional[BiblicalVerse]:
        """Retrieve a verse by reference."""
        book = self.get_book(reference.book_id)
        if book:
            return book.get_verse(reference.chapter, reference.verse)
        return None


class TheologicalTermTracker:
    """Utility class for tracking theological terms across versions."""
    
    @staticmethod
    def find_elohim_singular_verbs(version: BibleVersion) -> List[BiblicalVerse]:
        """Find verses where אלהים appears with singular verbs."""
        results = []
        for book in version.books.values():
            for verse in book.verses.values():
                has_elohim = False
                has_singular_verb = False
                
                for tag in verse.morphology:
                    lemma = getattr(tag, "lemma", None)
                    number = getattr(tag, "number", None)
                    person = getattr(tag, "person", None)
                    raw_pos = getattr(tag, "pos", None)
                    pos_value = raw_pos.value if isinstance(raw_pos, POS) else raw_pos

                    # Check for ????? (plural form)
                    if lemma == "?????" and number == "plural":
                        has_elohim = True

                    # Check for singular verb
                    if (
                        pos_value == POS.VERB.value
                        and number == "singular"
                        and person == 3
                    ):
                        has_singular_verb = True
                if has_elohim and has_singular_verb:
                    results.append(verse)
                    
        return results
    
    @staticmethod
    def compare_hebrew_lxx_terms(hebrew_verse: BiblicalVerse, 
                                lxx_verse: BiblicalVerse, 
                                term: str) -> Dict[str, List[str]]:
        """Compare how a Hebrew term is rendered in the LXX."""
        hebrew_matches = [
            tag.word for tag in hebrew_verse.morphology
            if term in tag.lemma or (tag.root and term in tag.root)
        ]
        
        # This would need semantic alignment data
        # For now, return the structure
        return {
            "hebrew_forms": hebrew_matches,
            "lxx_renderings": [],  # Would be populated with aligned Greek
            "semantic_shift_notes": []
        }
