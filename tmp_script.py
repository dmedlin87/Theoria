from __future__ import annotations
import sqlite3, tempfile, shutil
from pathlib import Path
from sqlalchemy.orm import Session
from theo.application.facades import database as database_module
from theo.services.api.app.db.seeds import seed_contradiction_claims
from theo.services.api.app.db import seeds as seeds_module

work = Path(tempfile.mkdtemp())
db_path = work / 'legacy_disabled.db'
with sqlite3.connect(db_path) as connection:
    connection.executescript('''CREATE TABLE contradiction_seeds (
        id TEXT PRIMARY KEY,
        osis_a TEXT NOT NULL,
        osis_b TEXT NOT NULL,
        summary TEXT,
        source TEXT,
        tags TEXT,
        weight REAL,
        created_at TEXT
    );''')
print('created table')
engine = database_module.configure_engine(f'sqlite:///{db_path}')
engine = database_module.get_engine()
print('engine', engine)
sample_payload = [{'osis_a': 'Gen.1.1', 'osis_b': 'Gen.1.2', 'summary': 'Legacy row', 'source': 'test', 'tags': ['regression'], 'weight': 1.0, 'perspective': 'skeptical'}]
seeds_module._iter_seed_entries = lambda *paths: sample_payload
seeds_module._verse_bounds = lambda reference: (None, None)
seeds_module._verse_range = lambda reference: None
with Session(engine) as session:
    seed_contradiction_claims(session)
print('after seed')
engine.dispose()
database_module._engine = None
database_module._SessionLocal = None
print('disposed engine; touching via sqlite3')
try:
    conn = sqlite3.connect(db_path)
    conn.close()
    print('opened+closed direct connection')
except Exception as exc:
    print('direct connect failed', exc)
print('attempting unlink')
try:
    db_path.unlink()
    print('unlink succeeded')
except Exception as exc:
    print('unlink failed', exc)
finally:
    shutil.rmtree(work, ignore_errors=True)
