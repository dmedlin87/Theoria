import os, json, re

CARDS = "evidence/cards/cards.jsonl"
OUT = "evidence/cards_md"

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")

def ensure_dir(d):
    os.makedirs(d, exist_ok=True)

def load_cards():
    items = []
    with open(CARDS, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception as e:
                raise SystemExit(f"Invalid JSON line: {e}\nLine: {line[:120]}...")
    return items

def frontmatter(obj: dict) -> str:
    keys = [
        "id","title","claim","scope","mode","stability","confidence",
        "tags","created_at","updated_at"
    ]
    def yaml_escape(v):
        if isinstance(v, str):
            v = v.replace('"', '\\"')
            return f'"{v}"'
        if isinstance(v, list):
            inner = ", ".join([yaml_escape(x) for x in v])
            return f"[{inner}]"
        return str(v)
    lines = ["---"]
    for k in keys:
        if k in obj:
            lines.append(f"{k}: {yaml_escape(obj[k])}")
    lines.append("---")
    return "\n".join(lines)

def render_card_md(card: dict) -> str:
    fm = frontmatter(card)
    body = []
    body.append(f"# {card.get('title','(untitled)')}\n")
    body.append(f"**Claim:** {card.get('claim','')}\n")
    body.append(f"**Scope:** {card.get('scope','')}  |  **Mode:** {card.get('mode','')}  |  **Stability:** {card.get('stability','')}  |  **Confidence:** {card.get('confidence','')}\n")
    src = card.get("sources", {})
    prim = src.get("primary", [])
    sec = src.get("secondary", [])
    if prim or sec:
        body.append("## Sources")
        if prim:
            body.append("**Primary**")
            for s in prim:
                body.append(f"- {s}")
        if sec:
            body.append("")
            body.append("**Secondary**")
            for s in sec:
                body.append(f"- {s}")
        body.append("")
    quotes = card.get("quotes", [])
    if quotes:
        body.append("## Quotes")
        for q in quotes:
            body.append(f"> {q}")
        body.append("")
    args_for = card.get("arguments_for", [])
    if args_for:
        body.append("## Arguments For")
        for a in args_for:
            body.append(f"- {a}")
        body.append("")
    cps = card.get("counterpoints", [])
    if cps:
        body.append("## Counterpoints")
        for c in cps:
            body.append(f"- {c}")
        body.append("")
    oqs = card.get("open_questions", [])
    if oqs:
        body.append("## Open Questions")
        for q in oqs:
            body.append(f"- {q}")
        body.append("")
    return fm + "\n\n" + "\n".join(body) + "\n"

def main():
    ensure_dir(OUT)
    cards = load_cards()
    for c in cards:
        cid = c.get("id","no-id")
        title = c.get("title","untitled")
        slug = slugify(title)
        filename = f"{cid}-{slug}.md"
        path = os.path.join(OUT, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_card_md(c))
    print(f"Wrote {len(cards)} markdown files to {OUT}")

if __name__ == "__main__":
    main()
