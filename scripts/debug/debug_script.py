import sqlite3
from pathlib import Path

from sqlalchemy.orm import Session

from theo.application.facades.database import configure_engine, get_engine
from theo.services.api.app.db.seeds import _DATASET_TABLES, _add_missing_column

path = Path('temp_test.db')
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
session = Session(engine)

try:
    added = _add_missing_column(session, _DATASET_TABLES['contradiction'], 'perspective', dataset_label='contradiction')
    print('added', added)
finally:
    session.close()
    engine.dispose()
    path.unlink(missing_ok=True)
