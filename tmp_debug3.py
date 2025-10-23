import os

os.environ.setdefault("SETTINGS_SECRET_KEY", "test-secret-key")
os.environ.setdefault("THEO_API_KEYS", '["pytest-default-key"]')
os.environ.setdefault("THEO_ALLOW_INSECURE_STARTUP", "1")
os.environ.setdefault("THEORIA_ENVIRONMENT", "development")

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from theo.application.facades.database import configure_engine, get_engine, get_session
from theo.services.api.app.db.models import Base, Document
from theo.services.api.app.db.run_sql_migrations import run_sql_migrations
from theo.services.api.app.main import app

tmp_dir = tempfile.mkdtemp()
db_path = Path(tmp_dir) / 'api.sqlite'
configure_engine(f"sqlite:///{db_path}")
Base.metadata.create_all(bind=get_engine())
run_sql_migrations(get_engine())
engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

with Session(engine) as session:
    doc1 = Document(
        id='doc-1',
        title='Systematic Theology Vol 1',
        authors=['Louis Berkhof'],
        doi='10.1234/berkhof.vol1',
        source_url='https://example.com/berkhof',
        source_type='book',
        collection='Theology',
        year=1938,
        abstract='A comprehensive Reformed systematic theology.',
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    doc2 = Document(
        id='doc-2',
        title='Institutes of the Christian Religion',
        authors=['John Calvin'],
        source_type='book',
        collection='Theology',
        year=1536,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add_all([doc1, doc2])
    session.commit()

def override_session():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()

app.dependency_overrides[get_session] = override_session

with TestClient(app) as client:
    with patch('theo.services.api.app.routes.export.export_to_zotero', new=AsyncMock(return_value={'success': True, 'exported_count': 2, "failed_count": 0, 'errors': []})) as mock_export:
        response = client.post('/api/export/zotero', json={'document_ids': ['doc-1', 'doc-2'], 'api_key': 'test-api-key', 'user_id': '12345'})
        print('status', response.status_code)
        print('json', response.json())
        print('called args keys', list(mock_export.call_args.kwargs.keys()))

app.dependency_overrides.pop(get_session, None)
engine.dispose()
