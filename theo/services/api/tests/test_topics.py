from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from theo.services.api.app.analytics.topics import generate_topic_digest
from theo.services.api.app.core.database import get_engine
from theo.services.api.app.db.models import Document


def test_topic_digest_deduplicates_document_ids() -> None:
    engine = get_engine()
    with Session(engine) as session:
        doc_id = "dedup-topic-doc"
        topic = "Duplicate Topic"

        document = Document(
            id=doc_id,
            title="Deduplicated Topic Document",
            source_type="test",
            bib_json={"primary_topic": topic, "topics": [topic]},
            topics=[topic],
        )
        session.add(document)
        session.commit()

        digest = generate_topic_digest(
            session, since=datetime.now(UTC) - timedelta(days=1)
        )

        cluster = next((item for item in digest.topics if item.topic == topic), None)
        assert cluster is not None, digest
        assert cluster.new_documents == 1
        assert cluster.document_ids == [doc_id]

        session.delete(document)
        session.commit()
