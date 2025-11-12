"""AI-powered processor for biblical text morphological and semantic analysis."""

import json
import re
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

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


def _validate_chat_completions_client(ai_client: Any) -> None:
    """Ensure the provided AI client exposes chat.completions.create."""

    if ai_client is None:
        raise ValueError(
            "ai_client must provide chat.completions.create; received None"
        )

    chat = getattr(ai_client, "chat", None)
    if chat is None:
        raise ValueError(
            "ai_client must provide chat.completions.create; missing 'chat' attribute"
        )

    completions = getattr(chat, "completions", None)
    if completions is None:
        raise ValueError(
            "ai_client must provide chat.completions.create; missing 'chat.completions'"
        )

    create = getattr(completions, "create", None)
    if create is None or not callable(create):
        raise ValueError(
            "ai_client must provide chat.completions.create callable"
        )


def _safe_json_loads(content: str, max_size: int = 1024 * 1024) -> Any:
    """Safely parse JSON with size limits to prevent DoS attacks.
    
    Args:
        content: JSON string to parse
        max_size: Maximum allowed size in bytes (default: 1MB)
        
    Returns:
        Parsed JSON object, or None if parsing fails
        
    Raises:
        ValueError: If content exceeds size limit
    """
    if len(content) > max_size:
        raise ValueError(f"JSON content too large: {len(content)} bytes (max: {max_size})")
    
    try:
        return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None


class BiblicalAIProcessor:
    """AI processor for biblical text analysis using OpenAI/Anthropic APIs."""
    
    def __init__(self, ai_client, model_name: str = "gpt-4"):
        _validate_chat_completions_client(ai_client)
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
        
        # Step 4: Create AI metadata (using dynamic confidence based on results)
        confidence_scores = self._calculate_confidence_scores(morphology, semantic_analysis)
        
        ai_analysis = AIAnalysis(
            generated_at=datetime.now(UTC),
            model_version=self.model_name,
            confidence_scores=confidence_scores
        )
        
        return BiblicalVerse(
            reference=reference,
            language=Language.HEBREW,
            text=text_content,
            morphology=morphology,
            semantic_analysis=semantic_analysis,
            ai_analysis=ai_analysis
        )
    
    def _calculate_confidence_scores(self, morphology: List[MorphologicalTag], 
                                   semantic_analysis: SemanticAnalysis) -> Dict[str, float]:
        """Calculate realistic confidence scores based on analysis results."""
        
        # Base confidence on actual content quality
        morphology_confidence = 0.75  # Conservative baseline
        if morphology:
            # Higher confidence if we have detailed morphological data
            has_detailed_tags = sum(1 for tag in morphology 
                                  if tag.lemma and tag.root and tag.gloss)
            morphology_confidence = min(0.95, 0.60 + (has_detailed_tags / len(morphology)) * 0.35)
        
        semantics_confidence = 0.70  # Conservative baseline
        if semantic_analysis.themes or semantic_analysis.theological_keywords:
            # Higher confidence if we found theological content
            theme_count = len(semantic_analysis.themes)
            keyword_count = len(semantic_analysis.theological_keywords)
            content_richness = min(1.0, (theme_count + keyword_count) / 10)
            semantics_confidence = 0.60 + content_richness * 0.30
        
        theological_confidence = 0.65  # Most conservative
        if semantic_analysis.cross_references or semantic_analysis.textual_variants:
            # Boost confidence if we have cross-references or variants
            theological_confidence = min(0.85, theological_confidence + 0.15)
            
        return {
            "morphology": round(morphology_confidence, 2),
            "semantics": round(semantics_confidence, 2),
            "theological_significance": round(theological_confidence, 2)
        }
    
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
        """Generate transliteration using AI with proper error handling."""
        
        prompt = f"""
Transliterate this Hebrew text into Latin characters following academic standards:

Hebrew: {hebrew_text}

Provide only the transliteration, no explanations.
"""
        
        try:
            response = self.ai_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception:
            # Fallback to basic transliteration if AI fails
            return "[transliteration unavailable]"
    
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
        
        try:
            response = self.ai_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            # Use safe JSON parsing with size limits
            morphology_data = _safe_json_loads(
                response.choices[0].message.content,
                max_size=512 * 1024  # 512KB limit for morphology data
            )
        except Exception:
            return []  # Return empty list on any error

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
        
        try:
            response = self.ai_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            # Use safe JSON parsing with size limits
            raw_semantic_data = _safe_json_loads(
                response.choices[0].message.content,
                max_size=256 * 1024  # 256KB limit for semantic data
            )
        except Exception:
            raw_semantic_data = None

        if not isinstance(raw_semantic_data, dict):
            return SemanticAnalysis(
                themes=[],
                theological_keywords=[],
                cross_references=[],
                textual_variants=[]
            )

        return SemanticAnalysis(
            themes=self._safe_string_list(raw_semantic_data.get("themes", [])),
            theological_keywords=self._safe_string_list(raw_semantic_data.get("theological_keywords", [])),
            cross_references=self._safe_string_list(raw_semantic_data.get("cross_references", [])),
            textual_variants=self._safe_string_list(raw_semantic_data.get("textual_variants", [])),
            translation_notes=self._safe_dict(raw_semantic_data.get("translation_notes", {}))
        )

    @staticmethod
    def _safe_string_list(candidate: Optional[List[str]]) -> List[str]:
        """Return a list of strings, discarding malformed AI payloads."""
        if not isinstance(candidate, list):
            return []
        # Limit list size and string length to prevent abuse
        safe_list = []
        for item in candidate[:50]:  # Max 50 items
            if isinstance(item, str) and len(item) <= 500:  # Max 500 chars per item
                safe_list.append(item)
        return safe_list

    @staticmethod
    def _safe_dict(candidate: Optional[Dict]) -> Dict:
        """Ensure translation notes are a safe dictionary."""
        if not isinstance(candidate, dict):
            return {}
        
        # Limit dictionary size and key/value lengths
        safe_dict = {}
        for key, value in list(candidate.items())[:20]:  # Max 20 entries
            if isinstance(key, str) and len(key) <= 100:  # Max 100 chars for keys
                if isinstance(value, str) and len(value) <= 1000:  # Max 1000 chars for values
                    safe_dict[key] = value
        return safe_dict


class CrossLanguageComparator:
    """AI-powered cross-language comparison for Hebrew/Greek texts."""

    def __init__(self, ai_client, model_name: str = "gpt-4"):
        _validate_chat_completions_client(ai_client)
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
        
        try:
            response = self.ai_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            # Use safe JSON parsing with size limits
            result = _safe_json_loads(
                response.choices[0].message.content,
                max_size=128 * 1024  # 128KB limit for comparison data
            )
            return result if isinstance(result, dict) else {"error": "Failed to parse AI response"}
        except Exception as exc:
            return {"error": f"Analysis failed: {str(exc)}"}


class TheologicalDebateAnalyzer:
    """AI analyzer for theological debate contexts."""

    def __init__(self, ai_client, model_name: str = "gpt-4"):
        _validate_chat_completions_client(ai_client)
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
        
        try:
            response = self.ai_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            # Use safe JSON parsing with size limits
            result = _safe_json_loads(
                response.choices[0].message.content,
                max_size=256 * 1024  # 256KB limit for theological analysis
            )
            return result if isinstance(result, dict) else {"error": "Failed to parse AI response"}
        except Exception as exc:
            return {"error": f"Analysis failed: {str(exc)}"}
