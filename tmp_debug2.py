from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from theo.services.api.app.db.models import Base, Document
from theo.services.api.app.models.export import ZoteroExportRequest

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
rows = session.execute(select(Document).where(Document.id.in_(payload.document_ids))).scalars()
document_index = {row.id: row for row in rows}
missing = [doc_id for doc_id in payload.document_ids if doc_id not in document_index]
print('document_index keys:', list(document_index.keys()))
print('missing:', missing)
