# Biblical Text Schema Design

## Overview

Design for storing multi-layer biblical texts with AI-enhanced morphological and semantic analysis.
Supports Hebrew Bible (Masoretic), Septuagint (LXX), and cross-translation research.

## Data Structure

### 1. Base Text Storage

```text
data/bibles/
├── hebrew-wlc/              # Westminster Leningrad Codex
│   ├── manifest.yaml
│   ├── genesis.jsonl
│   ├── exodus.jsonl
│   └── ...
├── greek-lxx-rahlfs/        # Septuagint (Rahlfs edition)
│   ├── manifest.yaml
│   ├── genesis.jsonl
│   └── ...
├── greek-na28/              # Nestle-Aland 28th (NT)
│   ├── manifest.yaml
│   ├── matthew.jsonl
│   └── ...
└── english-kjv/             # English for comparison
    ├── manifest.yaml
    └── ...
```

### 2. Verse Record Schema

```json
{
  "reference": {
    "book": "Genesis",
    "chapter": 1,
    "verse": 1,
    "book_id": "gen",
    "osisID": "Gen.1.1"
  },
  "text": {
    "raw": "בְּרֵאשִׁית בָּרָא אֱלֹהִים אֵת הַשָּׁמַיִם וְאֵת הָאָרֶץ",
    "normalized": "בראשית ברא אלהים את השמים ואת הארץ",
    "transliteration": "bereshit bara elohim et hashamayim ve'et ha'aretz"
  },
  "morphology": [
    {
      "word": "בְּרֵאשִׁית",
      "lemma": "ראשית",
      "root": "ראש",
      "pos": "noun",
      "gender": "feminine",
      "number": "singular",
      "state": "construct",
      "prefix": "ב",
      "gloss": "beginning"
    },
    {
      "word": "בָּרָא",
      "lemma": "ברא",
      "root": "ברא",
      "pos": "verb",
      "stem": "qal",
      "tense": "perfect",
      "person": 3,
      "gender": "masculine",
      "number": "singular",
      "gloss": "create"
    },
    {
      "word": "אֱלֹהִים",
      "lemma": "אלהים",
      "root": "אלה",
      "pos": "noun",
      "gender": "masculine",
      "number": "plural",
      "state": "absolute",
      "gloss": "God/gods",
      "theological_notes": ["plural_form_with_singular_verb", "divine_name"]
    }
  ],
  "semantic_analysis": {
    "themes": ["creation", "divine_activity", "cosmology"],
    "theological_keywords": ["אלהים", "ברא"],
    "cross_references": ["John.1.1", "Heb.11.3"],
    "textual_variants": [],
    "translation_notes": {
      "lxx_comparison": "ἐν ἀρχῇ ἐποίησεν ὁ θεὸς",
      "semantic_shifts": ["ברא->ποιέω (create->make)"]
    }
  },
  "manuscript_data": {
    "source": "WLC",
    "variants": [],
    "masoretic_notes": [],
    "critical_apparatus": []
  },
  "ai_analysis": {
    "generated_at": "2025-10-26T07:06:00Z",
    "model_version": "gpt-4",
    "confidence_scores": {
      "morphology": 0.95,
      "semantics": 0.88,
      "theological_significance": 0.92
    }
  }
}
```

### 3. Manifest Schema

```yaml
# data/bibles/hebrew-wlc/manifest.yaml
name: "Westminster Leningrad Codex"
abbreviation: "WLC"
language: "hebrew"
script: "hebrew"
license: "Public Domain"
source_url: "https://www.tanach.us/Tanach.xml"
version: "4.20"
description: "Masoretic Hebrew Bible based on Leningrad Codex"
features:
  - morphology
  - masoretic_notes
  - cantillation
  - vowel_points
books:
  - id: "gen"
    name: "Genesis"
    hebrew_name: "בראשית"
    chapters: 50
  - id: "exo"
    name: "Exodus"
    hebrew_name: "שמות"
    chapters: 40
  # ... etc
```

## AI Processing Pipeline

### Phase 1: Text Import & Normalization

```python
class BibleTextProcessor:
    def import_hebrew_text(self, source_file):
        """Import and normalize Hebrew text"""

    def generate_transliteration(self, hebrew_text):
        """AI-generated transliteration"""

    def extract_morphology(self, hebrew_text):
        """AI morphological analysis using GPT-4/Claude"""
```

### Phase 2: Cross-Language Analysis

```python
class CrossTranslationAnalyzer:
    def compare_hebrew_lxx(self, hebrew_verse, lxx_verse):
        """Semantic comparison Hebrew -> Greek"""

    def track_theological_terms(self, term, languages=['hebrew', 'greek', 'latin']):
        """Track key terms across translations"""

    def identify_translation_shifts(self, source_verse, target_verse):
        """AI-detected semantic/theological shifts"""
```

### Phase 3: Research Queries

```python
class TheologicalResearch:
    def search_divine_names(self, name_pattern):
        """Search יהוה, אלהים, etc. with grammatical context"""

    def analyze_plural_singulars(self):
        """Find אלהים with singular verbs (trinity debates)"""

    def compare_messianic_prophecies(self, reference):
        """Compare Hebrew vs LXX in key passages"""

    def track_textual_variants(self, passage):
        """Manuscript comparison for critical passages"""
```

## Implementation Plan

### Week 1: Foundation

- [ ] Create base schema and manifest structure
- [ ] Import WLC Genesis as proof of concept
- [ ] Basic morphological parsing with AI

### Week 2: Cross-Language Support

- [ ] Add LXX Genesis with alignment to Hebrew
- [ ] Implement semantic comparison framework
- [ ] Build theological term tracking

### Week 3: Research Features

- [ ] Advanced search capabilities
- [ ] Cross-reference generation
- [ ] Textual criticism support

### Week 4: AI Enhancement

- [ ] Automated analysis pipeline
- [ ] Confidence scoring
- [ ] Research hypothesis testing

## Research Use Cases

1. **Trinity/Divinity Debates**
   - Search אלהים plural + singular verbs
   - Track θεός usage in LXX divine contexts
   - Compare Christological passages Hebrew->Greek

2. **Textual Criticism**
   - Manuscript variants in key passages
   - LXX vs MT differences
   - Translation influence on doctrine

3. **Semantic Analysis**
   - Root word studies across languages
   - Theological term evolution
   - Context-sensitive meaning analysis

This schema provides the foundation for serious biblical scholarship within Theoria while leveraging your AI expertise for automated analysis.
