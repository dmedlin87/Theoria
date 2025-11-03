# Theoria Evidence Cards Module

Lightweight, schema-checked Evidence Cards for a YouTube-first, claim-sniffing workflow.

## Layout
- `evidence/cards/cards.jsonl` — canonical JSONL store (one card per line)
- `evidence/cards_md/` — generated Markdown mirrors
- `evidence/schemas/evidence_card.schema.json` — minimal schema (enforced by tooling)
- `scripts/evidence_tool.py` — lightweight validation/index/dossier helper
- `evidence/scripts/theoria_cli.py` — add/validate/search helper for cards.jsonl
- `evidence/scripts/build_markdown.py` — export Markdown mirrors
- `.github/workflows/validate-evidence-cards.yml` — CI for validate + build

## Commands
```bash
python scripts/evidence_tool.py validate
python scripts/evidence_tool.py index --jsonl evidence/registry/evidence.index.jsonl
python scripts/evidence_tool.py dossier --out evidence/registry
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
