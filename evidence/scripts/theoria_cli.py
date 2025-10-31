import argparse, json, os, uuid, datetime

CARDS = "evidence/cards/cards.jsonl"
SCHEMA = "evidence/schemas/evidence_card.schema.json"

ALLOWED_MODE = {"Skeptical","Neutral","Apologetic"}
ALLOWED_STABILITY = {"Low","Medium","High"}

def load_schema():
    with open(SCHEMA, "r", encoding="utf-8") as f:
        return json.load(f)

def load_cards():
    items = []
    if not os.path.exists(CARDS):
        return items
    with open(CARDS, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception as e:
                raise SystemExit(f"[cards.jsonl] Line {i} invalid JSON: {e}")
    return items

def save_card(obj):
    with open(CARDS, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def validate_obj(obj, schema):
    req = set(schema.get("required", []))
    missing = [k for k in req if k not in obj]
    if missing:
        return False, f"Missing required keys: {missing}"
    if obj["mode"] not in ALLOWED_MODE:
        return False, f"mode must be one of {sorted(ALLOWED_MODE)}"
    if obj["stability"] not in ALLOWED_STABILITY:
        return False, f"stability must be one of {sorted(ALLOWED_STABILITY)}"
    conf = obj["confidence"]
    if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
        return False, "confidence must be a number between 0 and 1"
    for k in ("quotes","arguments_for","counterpoints","open_questions","tags"):
        if not isinstance(obj.get(k, []), list):
            return False, f"{k} must be a list"
    src = obj.get("sources", {})
    if not isinstance(src.get("primary", []), list) or not isinstance(src.get("secondary", []), list):
        return False, "sources.primary and sources.secondary must be lists"
    prov = obj.get("provenance", {})
    if not isinstance(prov.get("kind",""), str) or not isinstance(prov.get("details",""), str):
        return False, "provenance.kind and provenance.details must be strings"
    return True, "ok"

def cmd_validate(_args):
    schema = load_schema()
    cards = load_cards()
    if not cards:
        print("No cards found. Nothing to validate.")
        return 0
    errors = 0
    for i, c in enumerate(cards, 1):
        ok, msg = validate_obj(c, schema)
        if not ok:
            errors += 1
            print(f"[INVALID] Card #{i} (id={c.get('id','?')}): {msg}")
    if errors == 0:
        print(f"All {len(cards)} cards valid ✓")
        return 0
    else:
        print(f"{errors} invalid card(s) found ✗")
        return 1

def cmd_add(args):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    obj = {
        "id": str(uuid.uuid4()),
        "title": args.title,
        "claim": args.claim,
        "scope": args.scope,
        "mode": args.mode,
        "stability": args.stability,
        "confidence": float(args.confidence),
        "sources": {
            "primary": [s.strip() for s in (args.sources_primary or "").split("|") if s.strip()],
            "secondary": [s.strip() for s in (args.sources_secondary or "").split("|") if s.strip()]
        },
        "quotes": [q.strip() for q in (args.quotes or "").split("|") if q.strip()],
        "arguments_for": [a.strip() for a in (args.arguments_for or "").split("|") if a.strip()],
        "counterpoints": [c.strip() for c in (args.counterpoints or "").split("|") if c.strip()],
        "open_questions": [o.strip() for o in (args.open_questions or "").split("|") if o.strip()],
        "tags": [t.strip() for t in (args.tags or "").split(",") if t.strip()],
        "provenance": {"kind": args.prov_kind or "manual", "details": args.prov_details or ""},
        "created_at": now,
        "updated_at": now
    }
    schema = load_schema()
    ok, msg = validate_obj(obj, schema)
    if not ok:
        raise SystemExit(f"Card invalid: {msg}")
    save_card(obj)
    print(f"Added card id={obj['id']}")
    return 0

def cmd_search(args):
    q = args.query.lower()
    cards = load_cards()
    hits = []
    for c in cards:
        hay = " ".join([
            c.get("title",""),
            c.get("claim",""),
            c.get("scope",""),
            " ".join(c.get("tags",[]))
        ]).lower()
        if all(tok in hay for tok in q.split()):
            hits.append(c)
    print(f"Found {len(hits)} result(s).")
    for i, c in enumerate(hits, 1):
        print(f"{i}. [{c.get('mode')}/{c.get('stability')}] {c.get('title')} (id={c.get('id')})")
        print(f"   scope={c.get('scope')}  tags={c.get('tags')}")
        clip = c.get("claim","")
        print(f"   claim={clip[:140]}{'...' if len(clip)>140 else ''}")
    return 0

def main():
    p = argparse.ArgumentParser(prog="theoria_cli.py")
    sub = p.add_subparsers(dest="cmd")
    v = sub.add_parser("validate", help="Validate cards.jsonl against schema")
    v.set_defaults(func=cmd_validate)
    a = sub.add_parser("add", help="Add a new card")
    a.add_argument("--title", required=True)
    a.add_argument("--claim", required=True)
    a.add_argument("--scope", required=True)
    a.add_argument("--mode", required=True, choices=sorted(list(ALLOWED_MODE)))
    a.add_argument("--stability", required=True, choices=sorted(list(ALLOWED_STABILITY)))
    a.add_argument("--confidence", required=True, type=float)
    a.add_argument("--tags")
    a.add_argument("--sources-primary")
    a.add_argument("--sources-secondary")
    a.add_argument("--quotes")
    a.add_argument("--arguments-for")
    a.add_argument("--counterpoints")
    a.add_argument("--open-questions")
    a.add_argument("--prov-kind")
    a.add_argument("--prov-details")
    a.set_defaults(func=cmd_add)
    s = sub.add_parser("search", help="Search cards (simple substring match)")
    s.add_argument("query")
    s.set_defaults(func=cmd_search)
    args = p.parse_args()
    if not hasattr(args, "func"):
        p.print_help()
        return 1
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
