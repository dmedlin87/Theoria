from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from theo.application.services import ApplicationContainer
from theo.domain import Document, DocumentId, DocumentMetadata
from theo.domain.research.overview import OverviewBullet, ReliabilityOverview
from theo.domain.research.scripture import Verse
from theo.infrastructure.api.app.main import app


@dataclass(slots=True)
class _FakeResearchService:
    verses: list[Verse]
    overview: ReliabilityOverview

    def fetch_passage(self, osis: str, translation: str | None = None) -> list[Verse]:
        if translation is None:
            return list(self.verses)
        return [
            Verse(
                osis=v.osis,
                translation=translation,
                text=v.text,
                book=v.book,
                chapter=v.chapter,
                verse=v.verse,
            )
            for v in self.verses
        ]

    def build_reliability_overview(
        self,
        *,
        osis: str,
        mode: str | None = None,
        note_limit: int = 3,
        manuscript_limit: int = 3,
    ) -> ReliabilityOverview:
        return self.overview


@pytest.fixture
def graphql_app_setup(monkeypatch: pytest.MonkeyPatch):
    sample_document = Document(
        id=DocumentId("doc-1"),
        metadata=DocumentMetadata(title="Sample", source="tests", language="en"),
        scripture_refs=("John.3.16",),
        tags=("featured",),
    )
    stored_documents: list[Document] = []

    verses = [
        Verse(
            osis="John.3.16",
            translation="SBLGNT",
            text="For God so loved the world",
            book="John",
            chapter=3,
            verse=16,
        )
    ]
    overview = ReliabilityOverview(
        osis="John.3.16",
        mode="apologetic",
        consensus=(OverviewBullet(summary="Summary A", citations=("John 3:16",)),),
        disputed=(),
        manuscripts=(OverviewBullet(summary="Manuscript detail", citations=("P66",)),),
    )
    research_service = _FakeResearchService(verses=verses, overview=overview)

    def _ingest_document(document: Document) -> DocumentId:
        stored_documents.append(document)
        return document.id

    def _get_document(document_id: DocumentId) -> Document | None:
        if document_id == sample_document.id:
            return sample_document
        for stored in stored_documents:
            if stored.id == document_id:
                return stored
        return None

    def _list_documents(*, limit: int = 20) -> list[Document]:
        results = [sample_document] + stored_documents
        return results[:limit]

    container = ApplicationContainer(
        ingest_document=_ingest_document,
        retire_document=lambda _doc_id: None,
        get_document=_get_document,
        list_documents=_list_documents,
        research_service_factory=lambda _session: research_service,
    )

    monkeypatch.setattr(
        "theo.infrastructure.api.app.graphql.context.resolve_application",
        lambda: (container, None),
    )

    return {
        "document": sample_document,
        "stored": stored_documents,
        "research_service": research_service,
    }


def _execute_graphql(query: str, variables: dict | None = None) -> dict:
    client = TestClient(app)
    response = client.post("/graphql", json={"query": query, "variables": variables})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("errors") is None, payload
    return payload["data"]


def test_documents_query_returns_documents(api_engine, graphql_app_setup):
    data = _execute_graphql(
        """
        query Documents($limit: Int!) {
          documents(limit: $limit) {
            id
            metadata { title source language }
            scriptureRefs
            tags
          }
        }
        """,
        {"limit": 10},
    )

    documents = data["documents"]
    assert documents[0]["id"] == str(graphql_app_setup["document"].id)
    assert documents[0]["metadata"]["title"] == "Sample"
    assert documents[0]["scriptureRefs"] == ["John.3.16"]
    assert documents[0]["tags"] == ["featured"]


def test_document_query_returns_single_document(api_engine, graphql_app_setup):
    data = _execute_graphql(
        """
        query Document($id: ID!) {
          document(id: $id) {
            id
            metadata { title source }
          }
        }
        """,
        {"id": str(graphql_app_setup["document"].id)},
    )

    assert data["document"]["metadata"]["source"] == "tests"


def test_document_query_unknown_id_returns_none(api_engine, graphql_app_setup):
    data = _execute_graphql(
        """
        query Document($id: ID!) {
          document(id: $id) {
            id
          }
        }
        """,
        {"id": "missing"},
    )

    assert data["document"] is None


def test_passage_query_returns_verses(api_engine, graphql_app_setup):
    data = _execute_graphql(
        """
        query Passage($osis: String!) {
          passage(osis: $osis) {
            osis
            translation
            text
          }
        }
        """,
        {"osis": "John.3.16"},
    )

    verse = data["passage"][0]
    assert verse["osis"] == "John.3.16"
    assert verse["text"].startswith("For God so loved")


def test_passage_query_respects_translation_argument(api_engine, graphql_app_setup):
    data = _execute_graphql(
        """
        query PassageWithTranslation($osis: String!, $translation: String!) {
          passage(osis: $osis, translation: $translation) {
            translation
            text
          }
        }
        """,
        {"osis": "John.3.16", "translation": "KJV"},
    )

    verse = data["passage"][0]
    assert verse["translation"] == "KJV"
    assert verse["text"].startswith("For God so loved")


def test_insights_query_flattens_overview(api_engine, graphql_app_setup):
    data = _execute_graphql(
        """
        query Insights($osis: String!) {
          insights(osis: $osis) {
            category
            summary
            citations
          }
        }
        """,
        {"osis": "John.3.16"},
    )

    insights = data["insights"]
    assert {insight["category"] for insight in insights} == {"consensus", "manuscript"}
    assert insights[0]["citations"]


def test_insights_query_includes_disputed_and_tracks_mode(
    api_engine, graphql_app_setup, monkeypatch
):
    research_service = graphql_app_setup["research_service"]
    existing = research_service.overview
    disputed_bullet = OverviewBullet(summary="Challenged reading", citations=("Source",))
    enriched_overview = ReliabilityOverview(
        osis=existing.osis,
        mode=existing.mode,
        consensus=existing.consensus,
        disputed=existing.disputed + (disputed_bullet,),
        manuscripts=existing.manuscripts,
    )
    monkeypatch.setattr(research_service, "overview", enriched_overview)

    captured: dict[str, str | None] = {}

    def capture_build_overview(
        self,
        *,
        osis: str,
        mode: str | None = None,
        note_limit: int = 3,
        manuscript_limit: int = 3,
    ) -> ReliabilityOverview:
        captured["mode"] = mode
        return self.overview

    monkeypatch.setattr(_FakeResearchService, "build_reliability_overview", capture_build_overview)

    data = _execute_graphql(
        """
        query InsightsWithMode($osis: String!, $mode: String) {
          insights(osis: $osis, mode: $mode) {
            category
            summary
          }
        }
        """,
        {"osis": "John.3.16", "mode": "skeptical"},
    )

    insights = data["insights"]
    assert {insight["category"] for insight in insights} == {
        "consensus",
        "disputed",
        "manuscript",
    }
    assert captured["mode"] == "skeptical"


def test_ingest_document_mutation_invokes_container(api_engine, graphql_app_setup):
    mutation = """
    mutation Ingest($input: DocumentInput!) {
      ingestDocument(input: $input) {
        documentId
      }
    }
    """
    payload = {
        "id": "doc-2",
        "metadata": {"title": "Second", "source": "tests"},
        "scriptureRefs": ["Genesis.1.1"],
        "tags": ["alpha"],
    }

    data = _execute_graphql(mutation, {"input": payload})

    assert data["ingestDocument"]["documentId"] == "doc-2"
    stored = graphql_app_setup["stored"]
    assert any(document.id == DocumentId("doc-2") for document in stored)
