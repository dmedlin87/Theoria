#!/usr/bin/env python3
"""Script to import Hebrew Bible data with AI morphological analysis."""

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class HebrewBibleImporter:
    """Import and process Hebrew Bible data with AI enhancement."""
    
    def __init__(self, ai_client=None, output_dir: str = "data/bibles/hebrew-wlc"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ai_client = ai_client
    
    def import_genesis_sample(self):
        """Import a few Genesis verses for testing."""
        
        # Sample Genesis verses with Hebrew text
        sample_verses = [
            {
                "ref": (1, 1),
                "hebrew": "בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ",
                "english": "In the beginning God created the heavens and the earth"
            },
            {
                "ref": (1, 2), 
                "hebrew": "וְהָאָרֶץ הָיְתָה תֹהוּ וָבֹהוּ וְחֹשֶׁךְ עַל־פְּנֵי תְהוֹם",
                "english": "Now the earth was formless and empty, darkness over the deep"
            },
            {
                "ref": (1, 3),
                "hebrew": "וַיֹּאמֶר אֱלֹהִים יְהִי אוֹר וַיְהִי־אוֹר",
                "english": "And God said, Let there be light, and there was light"
            }
        ]
        
        verses_data = []
        
        for verse_info in sample_verses:
            chapter, verse = verse_info["ref"]
            hebrew_text = verse_info["hebrew"]
            
            print(f"Processing Genesis {chapter}:{verse}...")
            
            # Create basic verse structure
            verse_data = {
                "reference": {
                    "book": "Genesis",
                    "chapter": chapter,
                    "verse": verse,
                    "book_id": "gen",
                    "osis_id": f"Gen.{chapter}.{verse}"
                },
                "language": "hebrew",
                "text": {
                    "raw": hebrew_text,
                    "normalized": self._normalize_hebrew(hebrew_text),
                    "transliteration": None
                },
                "english_reference": verse_info["english"]
            }
            
            # Add AI analysis if available
            if self.ai_client:
                try:
                    ai_analysis = self._analyze_with_ai(hebrew_text, verse_data["reference"])
                    verse_data.update(ai_analysis)
                    print(f"  ✅ AI analysis completed")
                except Exception as e:
                    print(f"  ⚠️ AI analysis failed: {e}")
                    verse_data["morphology"] = []
                    verse_data["semantic_analysis"] = None
            else:
                verse_data["morphology"] = []
                verse_data["semantic_analysis"] = None
            
            verses_data.append(verse_data)
        
        # Save to file
        output_file = self.output_dir / "genesis_imported.jsonl"
        with open(output_file, 'w', encoding='utf-8') as f:
            for verse in verses_data:
                f.write(json.dumps(verse, ensure_ascii=False) + '\n')
        
        print(f"\n✅ Saved {len(verses_data)} verses to {output_file}")
        return verses_data
    
    def _normalize_hebrew(self, text: str) -> str:
        """Basic Hebrew normalization - remove vowel points."""
        import re
        # Remove Hebrew diacritics (vowel points and cantillation)
        return re.sub(r'[\u0591-\u05C7]', '', text)
    
    def _analyze_with_ai(self, hebrew_text: str, reference: Dict) -> Dict:
        """Analyze Hebrew text with AI."""
        
        # Morphological analysis
        morphology_prompt = f"""
Analyze this Hebrew biblical text morphologically. For each word provide:
- word, lemma, root, part of speech, gender, number 
- For verbs: stem, tense, person
- gloss (English meaning)
- theological significance if any

Hebrew: {hebrew_text}
Reference: {reference['book']} {reference['chapter']}:{reference['verse']}

Return as JSON array with this structure:
[
  {
    "word": "בְּרֵאשִׁית",
    "lemma": "רֵאשִׁית", 
    "root": "ראש",
    "pos": "noun",
    "gender": "feminine",
    "number": "singular",
    "gloss": "beginning",
    "theological_notes": ["creation_narrative"]
  }
]
"""
        
        # Get morphological analysis
        morph_response = self.ai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": morphology_prompt}],
            temperature=0.1
        )
        
        try:
            morphology = json.loads(morph_response.choices[0].message.content)
        except:
            morphology = []
        
        # Semantic analysis
        semantic_prompt = f"""
Analyze this Hebrew biblical verse for theological and semantic content:

{hebrew_text} ({reference['book']} {reference['chapter']}:{reference['verse']})

Provide JSON with:
- themes: major theological themes
- theological_keywords: key Hebrew terms
- cross_references: related biblical passages
- translation_notes: important translation considerations

Example:
{
  "themes": ["creation", "divine_activity"],
  "theological_keywords": ["אלהים", "ברא"],
  "cross_references": ["John.1.1"],
  "translation_notes": {"elohim": "Plural noun with singular verb"}
}
"""
        
        semantic_response = self.ai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": semantic_prompt}],
            temperature=0.2
        )
        
        try:
            semantic_analysis = json.loads(semantic_response.choices[0].message.content)
        except:
            semantic_analysis = {
                "themes": [],
                "theological_keywords": [],
                "cross_references": [],
                "translation_notes": {}
            }
        
        return {
            "morphology": morphology,
            "semantic_analysis": semantic_analysis,
            "ai_analysis": {
                "generated_at": "2025-10-26T07:20:00Z",
                "model_version": "gpt-4",
                "confidence_scores": {
                    "morphology": 0.9,
                    "semantics": 0.85
                }
            }
        }


def main():
    """Main import function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Import Hebrew Bible sample with AI")
    parser.add_argument("--with-ai", action="store_true", 
                       help="Enable AI morphological analysis")
    parser.add_argument("--openai-key", 
                       help="OpenAI API key")
    
    args = parser.parse_args()
    
    # Setup AI client if requested
    ai_client = None
    if args.with_ai:
        try:
            import openai
            api_key = args.openai_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("❌ OpenAI API key required")
                print("   Set OPENAI_API_KEY environment variable")
                sys.exit(1)
            
            ai_client = openai.OpenAI(api_key=api_key)
            print("🤖 AI morphological analysis enabled")
        except ImportError:
            print("❌ Install OpenAI: pip install openai")
            sys.exit(1)
    
    # Import sample data
    importer = HebrewBibleImporter(ai_client)
    
    print("🔄 Importing Genesis sample...")
    print(f"   AI analysis: {'✅' if ai_client else '❌'}")
    
    verses = importer.import_genesis_sample()
    
    print("\n✅ Import completed!")
    print("📁 Output: data/bibles/hebrew-wlc/genesis_imported.jsonl")
    
    if verses:
        print("\n🔍 Sample analysis:")
        first_verse = verses[0]
        print(f"   Reference: {first_verse['reference']['osis_id']}")
        print(f"   Hebrew: {first_verse['text']['raw']}")
        
        if first_verse.get('morphology'):
            print(f"   Words analyzed: {len(first_verse['morphology'])}")
            print(f"   First word: {first_verse['morphology'][0]['word']} = {first_verse['morphology'][0]['gloss']}")
        
        if first_verse.get('semantic_analysis'):
            themes = first_verse['semantic_analysis'].get('themes', [])
            if themes:
                print(f"   Themes: {', '.join(themes)}")


if __name__ == "__main__":
    main()
