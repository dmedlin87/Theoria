import sqlite3
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from theo.application.facades.database import configure_engine, get_engine
from theo.infrastructure.api.app.db import seeds as seeds_module
from theo.infrastructure.api.app.db.seeds import seed_contradiction_claims

path = Path('temp_seed.db')
if path.exists():
    path.unlink()

with sqlite3.connect(path) as connection:
    connection.executescript('''
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

configure_engine(f'sqlite:///{path}')
engine = get_engine()

sample_payload = [{
    'osis_a': 'Gen.1.1',
    'osis_b': 'Gen.1.2',
    'summary': 'Legacy row',
    'source': 'test',
    'tags': ['regression'],
    'weight': 1.0,
    'perspective': 'skeptical',
}]

seeds_module._iter_seed_entries = lambda *paths: sample_payload
seeds_module._verse_bounds = lambda reference: (None, None)
seeds_module._verse_range = lambda reference: None

with Session(engine) as session:
    seed_contradiction_claims(session)
    value = session.execute(text('SELECT perspective FROM contradiction_seeds ORDER BY id LIMIT 1')).scalar_one()
    print('value', value)

with engine.connect() as connection:
    result = connection.exec_driver_sql("PRAGMA table_info('contradiction_seeds')")
    has_perspective = any(row[1] == 'perspective' for row in result)
    print('has perspective', has_perspective)
    result.close()

engine.dispose()
path.unlink(missing_ok=True)
print('unlinked')
