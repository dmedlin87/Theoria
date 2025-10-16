import sqlite3
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import text
from theo.services.api.app.db import seeds as seeds_module
from theo.services.api.app.db.seeds import seed_contradiction_claims
from theo.application.facades.database import configure_engine, get_engine

path = Path('temp_seed.db')
if path.exists():
    path.unlink()

conn = sqlite3.connect(path)
conn.executescript('''
CREATE TABLE contradiction_seeds (
    id TEXT PRIMARY KEY,
    osis_a TEXT NOT NULL,
    osis_b TEXT NOT NULL,
    summary TEXT,
    source TEXT,
    tags TEXT,
    weight REAL,
    created_at TEXT
);
''')
conn.close()

configure_engine(f'sqlite:///{path}')
engine = get_engine()

sample_payload = [
    {
        'osis_a': 'Gen.1.1',
        'osis_b': 'Gen.1.2',
        'summary': 'Legacy row',
        'source': 'test',
        'tags': ['regression'],
        'weight': 1.0,
        'perspective': 'skeptical',
    }
]

seeds_module._iter_seed_entries = lambda *paths: sample_payload
seeds_module._verse_bounds = lambda reference: (None, None)
seeds_module._verse_range = lambda reference: None

session = Session(engine)
try:
    seed_contradiction_claims(session)
    result = session.execute(text("SELECT perspective FROM contradiction_seeds ORDER BY id LIMIT 1"))
    try:
        value = result.scalar_one()
        print('value', value)
    except Exception as exc:
        print('query failed', exc)
finally:
    session.close()
    engine.dispose()
    path.unlink(missing_ok=True)
