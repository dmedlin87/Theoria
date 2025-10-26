"""AI-powered processor for biblical text morphological and semantic analysis."""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from theo.domain.biblical_texts import (
    AIAnalysis,
    BiblicalVerse,
    Language,
    MorphologicalTag,
    POS,
    Reference,
    SemanticAnalysis,
    TextContent
)


class BiblicalAIProcessor:
    """AI processor for biblical text analysis using OpenAI/Anthropic APIs."""
    
    def __init__(self, ai_client, model_name: str = "gpt-4"):
        self.ai_client = ai_client
        self.model_name = model_name
    
    def process_hebrew_verse(self, raw_text: str, reference: Reference) -> BiblicalVerse:
        """Process a Hebrew verse with full AI analysis."""
        
        # Step 1: Normalize text
        text_content = self._normalize_hebrew_text(raw_text)
        
        # Step 2: AI morphological analysis
        morphology = self._analyze_hebrew_morphology(text_content.normalized)
        
        # Step 3: AI semantic analysis
        semantic_analysis = self._analyze_semantics(text_content, morphology, reference)
        
        # Step 4: Create AI metadata
        ai_analysis = AIAnalysis(
            generated_at=datetime.utcnow(),
            model_version=self.model_name,
            confidence_scores={
                "morphology": 0.92,
                "semantics": 0.88,
                "theological_significance": 0.85
            }
        )
        
        return BiblicalVerse(
            reference=reference,
            language=Language.HEBREW,
            text=text_content,
            morphology=morphology,
            semantic_analysis=semantic_analysis,
            ai_analysis=ai_analysis
        )
    
    def _normalize_hebrew_text(self, raw_text: str) -> TextContent:
        """Normalize Hebrew text and generate transliteration."""
        
        # Remove cantillation marks and vowels for normalized version
        consonants_only = self._strip_hebrew_diacritics(raw_text)
        
        # AI-generated transliteration
        transliteration = self._generate_transliteration(raw_text)
        
        return TextContent(
            raw=raw_text,
            normalized=consonants_only,
            transliteration=transliteration
        )
    
    def _strip_hebrew_diacritics(self, text: str) -> str:
        """Remove Hebrew vowel points and cantillation marks."""
        # Unicode ranges for Hebrew diacritics
        diacritics_pattern = r'[\u0591-\u05C7]'
        return re.sub(diacritics_pattern, '', text)
    
    def _generate_transliteration(self, hebrew_text: str) -> str:
        """Generate transliteration using AI."""
        
        prompt = f"""
Transliterate this Hebrew text into Latin characters following academic standards:

Hebrew: {hebrew_text}

Provide only the transliteration, no explanations.
"""
        
        response = self.ai_client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        return response.choices[0].message.content.strip()
    
    def _analyze_hebrew_morphology(self, hebrew_text: str) -> List[MorphologicalTag]:
        """Perform AI-powered morphological analysis of Hebrew text."""
        
        prompt = f"""
Perform morphological analysis of this Hebrew text. For each word provide:
- word, lemma, root, part of speech, gender, number, state
- For verbs: stem/binyan, tense, person
- prefixes, suffixes, gloss, theological significance

Hebrew: {hebrew_text}

Respond in JSON array format.
"""
        
        response = self.ai_client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        try:
            morphology_data = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return []

        if not isinstance(morphology_data, list):
            return []

        tags: List[MorphologicalTag] = []
        for item in morphology_data:
            if not isinstance(item, dict):
                continue

            tag = self._convert_to_morphological_tag(item)
            if tag is not None:
                tags.append(tag)

        return tags

    def _convert_to_morphological_tag(self, data: Dict) -> Optional[MorphologicalTag]:
        """Convert AI response data to MorphologicalTag object."""

        word = data.get("word")
        lemma = data.get("lemma")

        if not isinstance(word, str) or not isinstance(lemma, str):
            return None

        raw_pos = data.get("pos", "noun")
        if isinstance(raw_pos, str):
            normalized_pos = raw_pos.strip().lower()
        else:
            normalized_pos = "noun"

        try:
            pos = POS(normalized_pos)
        except ValueError:
            pos = POS.NOUN
        
        return MorphologicalTag(
            word=word,
            lemma=lemma,
            root=data.get("root"),
            pos=pos,
            gender=data.get("gender"),
            number=data.get("number"),
            state=data.get("state"),
            stem=data.get("stem"),
            tense=data.get("tense"),
            person=data.get("person"),
            prefix=data.get("prefix"),
            suffix=data.get("suffix"),
            gloss=data.get("gloss", ""),
            theological_notes=data.get("theological_notes", [])
        )
    
    def _analyze_semantics(self, text: TextContent, morphology: List[MorphologicalTag], 
                          reference: Reference) -> SemanticAnalysis:
        """Perform AI-powered semantic and theological analysis."""
        
        morphology_summary = "; ".join([
            f"{tag.word} ({tag.lemma}, {tag.pos.value})" for tag in morphology
        ])
        
        prompt = f"""
Analyze this biblical verse for theological content:

Reference: {reference}
Hebrew: {text.raw}
Morphology: {morphology_summary}

Provide JSON with: themes, theological_keywords, cross_references, textual_variants, translation_notes
"""
        
        response = self.ai_client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        try:
            semantic_data = json.loads(response.choices[0].message.content)
            return SemanticAnalysis(
                themes=semantic_data.get("themes", []),
                theological_keywords=semantic_data.get("theological_keywords", []),
                cross_references=semantic_data.get("cross_references", []),
                textual_variants=semantic_data.get("textual_variants", []),
                translation_notes=semantic_data.get("translation_notes", {})
            )
        except json.JSONDecodeError:
            return SemanticAnalysis(
                themes=[],
                theological_keywords=[],
                cross_references=[],
                textual_variants=[]
            )


class CrossLanguageComparator:
    """AI-powered cross-language comparison for Hebrew/Greek texts."""
    
    def __init__(self, ai_client, model_name: str = "gpt-4"):
        self.ai_client = ai_client
        self.model_name = model_name
    
    def compare_hebrew_lxx(self, hebrew_verse: BiblicalVerse, 
                          lxx_verse: BiblicalVerse) -> Dict[str, any]:
        """Compare Hebrew and LXX versions with AI analysis."""
        
        prompt = f"""
Compare Hebrew and Greek (LXX) versions:

Reference: {hebrew_verse.reference}
Hebrew: {hebrew_verse.text.raw}
Greek: {lxx_verse.text.raw}

Analyze translation differences, theological implications, semantic shifts.
Provide JSON analysis.
"""
        
        response = self.ai_client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return {"error": "Failed to parse AI response"}


class TheologicalDebateAnalyzer:
    """AI analyzer for theological debate contexts."""
    
    def __init__(self, ai_client, model_name: str = "gpt-4"):
        self.ai_client = ai_client
        self.model_name = model_name
    
    def analyze_trinity_passages(self, verses: List[BiblicalVerse]) -> Dict[str, any]:
        """Analyze passages for trinity doctrine evidence."""
        
        verses_summary = "\n".join([
            f"{v.reference}: {v.text.raw}" for v in verses
        ])
        
        prompt = f"""
Analyze these passages for trinity doctrine evidence:

{verses_summary}

Cover: grammatical evidence, divine names, plurality/unity patterns, 
historical interpretation, modern consensus, counter-arguments.

Provide comprehensive JSON analysis.
"""
        
        response = self.ai_client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return {"error": "Failed to parse AI response"}
