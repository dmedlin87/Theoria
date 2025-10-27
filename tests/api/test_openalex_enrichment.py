import httpx
from sqlalchemy.orm import Session, sessionmaker

from theo.infrastructure.api.app.analytics.openalex_enrichment import (
    enrich_document_openalex_details,
)
from theo.adapters.persistence.models import Document


class _StubOpenAlexClient:
    def __init__(self) -> None:
        self.metadata_calls: list[dict] = []
        self.citation_calls: list[tuple[str, int | None]] = []

    def fetch_work_metadata(self, **kwargs):
        self.metadata_calls.append(kwargs)
        return {
            "id": "https://openalex.org/W123",
            "display_name": "Example Work",
            "doi": "10.1234/example",
            "authorships": [
                {"author": {"display_name": "Author One"}},
                {"author": {"display_name": "Author Two"}},
            ],
            "concepts": [
                {"display_name": "Theology", "score": 0.9},
                {"display_name": "Philosophy", "score": 0.8},
            ],
            "referenced_works": ["W10"],
            "cited_by_count": 42,
        }

    def fetch_citations(self, work_id: str, *, max_results: int | None = 50):
        self.citation_calls.append((work_id, max_results))
        return {
            "referenced": ["W10"],
            "cited_by": [
                {
                    "id": "https://openalex.org/W201",
                    "display_name": "Citing Work",
                    "doi": "10.2000/example",
                }
            ],
        }


def test_enrich_document_openalex_details_persists_metadata(api_engine) -> None:
    SessionLocal = sessionmaker(bind=api_engine)
    client = _StubOpenAlexClient()

    with SessionLocal() as session:  # type: Session
        document = Document(title="Example Work", doi="10.1234/example")
        session.add(document)
        session.commit()

        reloaded = session.get(Document, document.id)
        assert reloaded is not None

        updated = enrich_document_openalex_details(
            session, reloaded, openalex_client=client
        )
        assert updated is True
        session.commit()

        refreshed = session.get(Document, document.id)
        assert refreshed is not None
        assert refreshed.authors == ["Author One", "Author Two"]
        assert refreshed.bib_json["openalex"]["id"] == "W123"
        assert refreshed.bib_json["citations"] == [
            {
                "id": "https://openalex.org/W201",
                "display_name": "Citing Work",
                "doi": "10.2000/example",
            }
        ]
        assert refreshed.bib_json["references"] == ["W10"]
        assert refreshed.bib_json["topics"][:2] == ["Theology", "Philosophy"]
        assert refreshed.topics[:2] == ["Theology", "Philosophy"]


def test_enrich_document_openalex_details_handles_http_errors(api_engine) -> None:
    SessionLocal = sessionmaker(bind=api_engine)

    class _ErroringClient(_StubOpenAlexClient):
        def fetch_work_metadata(self, **kwargs):  # type: ignore[override]
            raise httpx.HTTPStatusError(
                "rate limited",
                request=httpx.Request("GET", "https://api.openalex.org/works/W123"),
                response=httpx.Response(429, request=httpx.Request("GET", "https://api.openalex.org/works/W123")),
            )

    client = _ErroringClient()

    with SessionLocal() as session:  # type: Session
        document = Document(title="Example Work", doi="10.1234/example")
        session.add(document)
        session.commit()

        reloaded = session.get(Document, document.id)
        assert reloaded is not None

        updated = enrich_document_openalex_details(
            session, reloaded, openalex_client=client
        )

        assert updated is False
        session.commit()
        refreshed = session.get(Document, document.id)
        assert refreshed is not None
        assert refreshed.bib_json is None

