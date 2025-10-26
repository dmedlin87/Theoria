# Biblical Text Analysis System for Theoria

📖 **Advanced multi-layer biblical text analysis with AI-enhanced morphological and semantic research capabilities.**

## Overview

This system provides sophisticated biblical text analysis specifically designed for theological research, textual criticism, and cross-translation studies. It combines traditional biblical scholarship with modern AI to deliver unprecedented research capabilities.

## 🎆 Key Features

### 🔍 **Multi-Layer Analysis**
- **Morphological**: Root, lemma, POS, grammatical features, theological significance
- **Semantic**: Themes, cross-references, theological keywords
- **AI-Enhanced**: GPT-4 powered analysis with confidence scoring
- **Cross-Translation**: Hebrew ↔ LXX ↔ English comparison

### ⚔️ **Theological Research**
- **Trinity Studies**: [translate:אלהים] + singular verb analysis
- **Divine Names**: [translate:יהוה], [translate:אדני], [translate:אל שדי] tracking across manuscripts
- **Messianic Prophecies**: Hebrew vs LXX comparison for Christological passages  
- **Textual Criticism**: Variant tracking and theological implications

### 📊 **Advanced Search**
- Root-based concordance (all forms of [translate:ברא], [translate:כפר], etc.)
- Grammatical pattern matching (plural nouns + singular verbs)
- Semantic field analysis (creation, covenant, atonement)
- Cross-reference networks

## 📦 Project Structure

```
theoria/
├── docs/
│   └── BIBLE_TEXT_SCHEMA.md      # Complete schema documentation
├── data/bibles/                # Biblical text storage
│   ├── hebrew-wlc/              # Westminster Leningrad Codex
│   ├── greek-lxx-rahlfs/        # Septuagint (Rahlfs)
│   └── english-kjv/             # King James Version
├── theo/domain/
│   └── biblical_texts.py        # Core domain models
│   └── repositories/
│       └── biblical_texts.py    # Repository interfaces
├── theo/adapters/
│   └── biblical_ai_processor.py # AI morphological analysis
└── scripts/
    ├── import_hebrew_bible.py   # Data import with AI processing
    └── test_biblical_analysis.py # Demo & testing
```

## 🚀 Quick Start

### 1. Test the System
```bash
# Run the demonstration (no external dependencies)
python scripts/test_biblical_analysis.py
```

This will show:
- Morphological analysis of Genesis 1:1 ([translate:בְּרֵאשִׁית בָּרָא אֱלֹהִים...])
- Trinity research capabilities ([translate:אלהים] plural + singular verb)
- Search and theological term tracking

### 2. Import Real Hebrew Bible Data
```bash
# Install OpenAI for AI analysis
pip install openai

# Set your OpenAI API key
export OPENAI_API_KEY="your-key-here"

# Import Genesis with AI morphological analysis
python scripts/import_hebrew_bible.py --with-ai
```

### 3. Explore the Results
```bash
# View the imported data
head -1 data/bibles/hebrew-wlc/genesis_imported.jsonl | jq .

# See morphological analysis
jq '.morphology[0]' data/bibles/hebrew-wlc/genesis_imported.jsonl

# View semantic analysis
jq '.semantic_analysis' data/bibles/hebrew-wlc/genesis_imported.jsonl
```

## 📊 Example Analysis Output

### Genesis 1:1 Morphological Analysis
```json
{
  "word": "אֱלֹהִים",
  "lemma": "אלהים",
  "root": "אלה",
  "pos": "noun",
  "gender": "masculine",
  "number": "plural",
  "state": "absolute",
  "gloss": "God",
  "theological_notes": [
    "divine_name",
    "plural_form_singular_verb",
    "trinity_evidence"
  ]
}
```

### Trinity Research Results
```json
{
  "elohim_singular_verbs": [
    {
      "reference": "Gen.1.1",
      "evidence": "אלהים (plural) + ברא (singular verb)",
      "theological_significance": "Grammatical plurality with verbal unity"
    }
  ]
}
```

## ⚔️ Advanced Theological Research

### Trinity Evidence Analysis
```python
from theo.domain.repositories.biblical_texts import CrossTranslationAnalyzer

analyzer = CrossTranslationAnalyzer(biblical_repo, research_repo)

# Comprehensive trinity analysis
trinity_evidence = analyzer.analyze_trinity_evidence()
print(trinity_evidence['elohim_singular_verbs'])
print(trinity_evidence['divine_plural_references'])
```

### Divine Names Study
```python
# Track all divine name usage patterns
divine_analysis = analyzer.analyze_divine_names_study()

# Compare Hebrew vs LXX renderings
for name in ["יהוה", "אלהים", "אדני"]:
    lxx_renderings = divine_analysis[name]['lxx_renderings']
    print(f"{name} → {lxx_renderings}")
```

### Messianic Prophecy Comparison
```python
# Analyze key Christological passages
messianic_analysis = analyzer.analyze_messianic_prophecies()

# Isaiah 7:14 - virgin birth debate
isa_714 = messianic_analysis['Isa.7.14']
print(f"Hebrew: {isa_714['hebrew'].text.raw}")
print(f"LXX: {isa_714['lxx'].text.raw}")
print(f"Key difference: {isa_714['comparison']['key_differences']}")
```

## 📚 Data Sources & Licensing

### Hebrew Bible
- **Westminster Leningrad Codex (WLC)** - Public Domain
- **Source**: https://www.tanach.us/
- **Features**: Vowel points, cantillation, Masoretic notes

### Greek Septuagint (Planned)
- **Rahlfs Edition** - Public Domain portions
- **Göttingen Septuagint** - Where permissible
- **Features**: Critical apparatus, manuscript variants

### AI Analysis
- **Model**: GPT-4 (configurable)
- **Confidence Scoring**: Morphology (>90%), Semantics (>85%)
- **Theological Focus**: Trinity, Messianic, Divine Names

## 🗺️ Roadmap

### Phase 1: Foundation ✅
- [x] Domain models and schema design
- [x] AI morphological processor
- [x] Hebrew Bible importer
- [x] Trinity research capabilities

### Phase 2: Expansion (Week 2-3)
- [ ] LXX Greek import and alignment
- [ ] Cross-translation semantic mapping
- [ ] Textual criticism features
- [ ] Advanced search interface

### Phase 3: Research Tools (Week 4+)
- [ ] Theological debate analyzer
- [ ] Manuscript variant tracking
- [ ] Historical development analysis
- [ ] Export to academic formats

## 🤝 Contributing

This system is designed for serious biblical scholarship. Contributions welcome in:
- Additional Bible version support
- Enhanced AI analysis prompts
- Theological research methodologies
- Performance optimizations

## 📜 Academic Applications

Perfect for:
- **Seminary coursework** - Trinity, Christology, Biblical theology
- **Doctoral research** - Textual criticism, translation studies  
- **Apologetics** - Cross-referencing theological arguments
- **Pastoral study** - Deep exegetical analysis
- **Interfaith dialogue** - Comparative textual analysis

---

🚀 **Ready to revolutionize your biblical research?** 

Start with `python scripts/test_biblical_analysis.py` to see the system in action, then add your OpenAI key and import real Hebrew Bible data for full morphological analysis.

The combination of traditional biblical scholarship with modern AI creates unprecedented research capabilities for theological study and debate analysis.
