import asyncio
from datetime import datetime, UTC
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch
from theo.services.api.app.db.models import Base, Document
from theo.services.api.app.models.export import ZoteroExportRequest
from theo.services.api.app.routes.export import export_to_zotero_endpoint

engine = create_engine('sqlite://', future=True)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
session = SessionLocal()

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

payload = ZoteroExportRequest(document_ids=['doc-1', 'doc-2'], api_key='key', user_id='123')

async def dummy_export(**kwargs):
    print('dummy_export called with', kwargs.keys())
    return {'success': True, 'exported_count': 2, 'failed_count': 0, 'errors': []}

async def main():
    with patch('theo.services.api.app.routes.export.export_to_zotero', new=dummy_export):
        result = await export_to_zotero_endpoint(payload, session=session)
        print('result', result)

asyncio.run(main())
