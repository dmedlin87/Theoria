# Theoria Evidence Cards Module

Lightweight, schema-checked Evidence Cards for a YouTube-first, claim-sniffing workflow.

## Layout
- `evidence/cards/cards.jsonl` — canonical JSONL store (one card per line)
- `evidence/cards_md/` — generated Markdown mirrors
- `evidence/schemas/evidence_card.schema.json` — minimal schema (enforced by CLI)
- `evidence/scripts/theoria_cli.py` — add/validate/search (no dependencies)
- `evidence/scripts/build_markdown.py` — export Markdown mirrors
- `.github/workflows/validate-evidence-cards.yml` — CI for validate + build

## Commands
```bash
python evidence/scripts/theoria_cli.py validate
python evidence/scripts/build_markdown.py
python evidence/scripts/theoria_cli.py search "Luke census"
```

## Add a card

```bash
python evidence/scripts/theoria_cli.py add \
  --title "..." --claim "..." --scope "..." \
  --mode Skeptical --stability High --confidence 0.9 \
  --tags "tag1,tag2" \
  --sources-primary "A|B" --sources-secondary "C|D" \
  --quotes "q1|q2" \
  --arguments-for "argA|argB" \
  --counterpoints "cpA|cpB" \
  --open-questions "oqA|oqB"
```

**Source of truth:** `cards.jsonl`. Rebuild mirrors whenever it changes.

```
