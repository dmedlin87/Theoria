from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query, Session

from theo.services.api.app.core import settings as settings_module
from theo.services.api.app.main import app
from theo.services.api.app.research.notes import get_notes_for_osis


def test_scripture_endpoint_returns_range() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/scripture",
            params={"osis": "John.1.1-2", "translation": "ESV"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["translation"] == "ESV"
        assert payload["meta"]["count"] == 2
        assert [verse["osis"] for verse in payload["verses"]] == [
            "John.1.1",
            "John.1.2",
        ]


def test_crossrefs_endpoint_returns_ranked_results() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/crossrefs", params={"osis": "John.1.1", "limit": 1}
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["results"][0]["target"] == "Genesis.1.1"


def test_variants_endpoint_returns_apparatus() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/variants",
            params={"osis": "John.1.1"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["total"] >= 2
        assert any(entry["category"] == "manuscript" for entry in payload["readings"])


def test_variants_endpoint_empty_for_unknown_reference() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/variants",
            params={"osis": "Obadiah.1.1"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["total"] == 0
        assert payload["readings"] == []


def test_reliability_overview_adjusts_by_mode() -> None:
    with TestClient(app) as client:
        supportive = client.post(
            "/research/notes",
            json={
                "osis": "John.1.1",
                "title": "Most early teachers say the verse supports Jesus.",
                "body": "Supportive note",
                "stance": "apologetic",
                "claim_type": "theological",
                "confidence": 0.9,
                "evidences": [
                    {
                        "citation": "Irenaeus, Against Heresies 3.1",
                        "source_ref": "Genesis.1.1",
                    }
                ],
            },
        )
        assert supportive.status_code == 201, supportive.text
        supportive_id = supportive.json()["note"]["id"]

        critical = client.post(
            "/research/notes",
            json={
                "osis": "John.1.1",
                "title": "Some scholars raise a tension in the wording.",
                "body": "Critical note",
                "stance": "critical",
                "claim_type": "textual",
                "confidence": 0.6,
                "evidences": [
                    {
                        "citation": "Bart D. Ehrman, Misquoting Jesus",
                        "source_ref": "Luke.1.1",
                    }
                ],
            },
        )
        assert critical.status_code == 201, critical.text
        critical_id = critical.json()["note"]["id"]

        apologetic_view = client.get(
            "/research/overview", params={"osis": "John.1.1", "mode": "apologetic"}
        )
        assert apologetic_view.status_code == 200, apologetic_view.text
        payload = apologetic_view.json()
        assert payload["mode"] == "apologetic"
        assert any(
            "supports Jesus" in item["summary"] for item in payload["consensus"]
        ), payload
        assert any(
            "raise a tension" in item["summary"] for item in payload["disputed"]
        ), payload
        assert payload["manuscripts"], payload
        assert payload["manuscripts"][0]["citations"], payload

        skeptical_view = client.get(
            "/research/overview", params={"osis": "John.1.1", "mode": "skeptical"}
        )
        assert skeptical_view.status_code == 200, skeptical_view.text
        skeptical_payload = skeptical_view.json()
        assert skeptical_payload["mode"] == "skeptical"
        assert any(
            "raise a tension" in item["summary"] for item in skeptical_payload["consensus"]
        ), skeptical_payload

        client.delete(f"/research/notes/{supportive_id}")
        client.delete(f"/research/notes/{critical_id}")


def test_morphology_endpoint_returns_tokens() -> None:
    with TestClient(app) as client:
        response = client.get("/research/morphology", params={"osis": "John.1.1"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["tokens"]
        token = payload["tokens"][0]
        assert token["surface"] == "\u1f18\u03bd"
        assert token["gloss"] == "in"


def test_notes_crud_roundtrip() -> None:
    with TestClient(app) as client:
        create = client.post(
            "/research/notes",
            json={
                "osis": "John.1.1",
                "body": "The Logos is identified with God.",
                "stance": "apologetic",
                "claim_type": "theological",
                "confidence": 0.8,
                "evidences": [
                    {
                        "source_type": "crossref",
                        "source_ref": "Genesis.1.1",
                        "snippet": "Creation prologue echoes.",
                        "osis_refs": ["Genesis.1.1"],
                    }
                ],
            },
        )
        assert create.status_code == 201
        note_id = create.json()["note"]["id"]

        listing = client.get("/research/notes", params={"osis": "John.1.1"})
        assert listing.status_code == 200
        payload = listing.json()
        assert payload["total"] == 1
        note = payload["notes"][0]
        assert note["id"] == note_id
        assert note["stance"] == "apologetic"
        assert note["evidences"][0]["source_ref"] == "Genesis.1.1"

        update = client.patch(
            f"/research/notes/{note_id}",
            json={
                "body": "The Logos is both divine and distinct.",
                "tags": ["prologue"],
                "evidences": [
                    {
                        "source_type": "crossref",
                        "source_ref": "Exodus.3.14",
                        "snippet": "I AM resonances.",
                        "osis_refs": ["Exodus.3.14"],
                    }
                ],
            },
        )
        assert update.status_code == 200, update.text
        updated_note = update.json()["note"]
        assert updated_note["body"] == "The Logos is both divine and distinct."
        assert updated_note["tags"] == ["prologue"]
        assert len(updated_note["evidences"]) == 1
        assert updated_note["evidences"][0]["source_ref"] == "Exodus.3.14"

        delete = client.delete(f"/research/notes/{note_id}")
        assert delete.status_code == 204, delete.text

        after = client.get("/research/notes", params={"osis": "John.1.1"})
        assert after.status_code == 200
        assert after.json()["total"] == 0
        assert after.json()["notes"] == []


def test_note_update_and_delete_missing_note_returns_404() -> None:
    with TestClient(app) as client:
        update = client.patch(
            "/research/notes/missing",
            json={"body": "No-op"},
        )
        assert update.status_code == 404

        delete = client.delete("/research/notes/missing")
        assert delete.status_code == 404


def test_historicity_endpoint_filters_and_limits() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/historicity",
            params={"query": "bethlehem", "year_from": 2015, "limit": 5},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["query"] == "bethlehem"
        assert payload["total"] >= 1
        assert all(
            item.get("year") is None or item["year"] >= 2015
            for item in payload["results"]
        )


def test_historicity_endpoint_empty_results() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/historicity",
            params={"query": "unknown subject"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["total"] == 0
        assert payload["results"] == []


def test_historicity_endpoint_rejects_invalid_year_range() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/historicity",
            params={"query": "bethlehem", "year_from": 2020, "year_to": 2000},
        )
        assert response.status_code == 422


def test_fallacies_endpoint_returns_detections() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/research/fallacies",
            json={
                "text": "Leading experts agree this is so and critics claim that believers worship idols.",
                "min_confidence": 0.3,
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["total"] >= 1
        assert any(hit["id"] == "straw-man" for hit in payload["detections"])


def test_fallacies_endpoint_requires_non_empty_text() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/research/fallacies",
            json={"text": "   "},
        )
        assert response.status_code == 422


def test_report_endpoint_combines_sections() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/research/report",
            json={
                "osis": "John.1.1",
                "stance": "apologetic",
                "historicity_query": "logos",
                "claims": [{"statement": "The Logos pre-exists creation."}],
                "include_fallacies": True,
                "narrative_text": "Leading experts agree this hymn preserves apostolic tradition.",
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()["report"]
        assert payload["osis"] == "John.1.1"
        assert payload["meta"]["variant_count"] >= 1
        assert any(section["title"].startswith("Stability") for section in payload["sections"])


def test_report_endpoint_requires_text_when_auditing_fallacies() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/research/report",
            json={
                "osis": "John.1.1",
                "stance": "apologetic",
                "include_fallacies": True,
            },
        )
        assert response.status_code == 422


def test_contradictions_by_osis_returns_items_and_is_stable_shape() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/contradictions",
            params=[("osis", "Luke.2.1-7"), ("topic", "chronology")],
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert "items" in payload
        assert payload["items"], "Expected seeded contradictions for Luke 2"
        first = payload["items"][0]
        assert first["osis_a"] == "Luke.2.1-7"
        assert first["osis_b"] == "Matthew.2.1-12"
        assert first["tags"] == ["chronology", "nativity"]
        assert (
            first["weight"] >= payload["items"][1]["weight"]
            if len(payload["items"]) > 1
            else True
        )


def test_geo_lookup_returns_places_with_confidence_and_aliases() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/research/geo/search",
            params={"query": "Bethlehem"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["items"], "Expected seeded geography entries"
        place = payload["items"][0]
        assert place["slug"] == "bethlehem"
        assert place["confidence"] >= 0.9
        assert "Bethlehem Ephrathah" in place["aliases"]


def test_features_exposed_in_discovery() -> None:
    with TestClient(app) as client:
        response = client.get("/features/discovery")
        assert response.status_code == 200
        payload = response.json()
        assert payload["features"]["research"] is True
        assert isinstance(payload["features"]["contradictions"], bool)
        assert isinstance(payload["features"]["geo"], bool)


def test_flags_off_returns_empty_items_but_200() -> None:
    settings = settings_module.get_settings()
    original_contra = settings.contradictions_enabled
    original_geo = settings.geo_enabled
    settings.contradictions_enabled = False
    settings.geo_enabled = False
    try:
        with TestClient(app) as client:
            contra = client.get(
                "/research/contradictions",
                params=[("osis", "Luke.2.1-7")],
            )
            geo = client.get("/research/geo/search", params={"query": "Bethlehem"})
            assert contra.status_code == 200
            assert contra.json()["items"] == []
            assert geo.status_code == 200
            assert geo.json()["items"] == []
    finally:
        settings.contradictions_enabled = original_contra
        settings.geo_enabled = original_geo


def test_get_notes_tag_filter_executes_with_postgres_dialect() -> None:
    compiled_sql: list[str] = []
    dialect = postgresql.dialect()

    original_all = Query.all

    def compile_with_postgres(self: Query) -> list[Any]:
        compiled = self.statement.compile(dialect=dialect)
        compiled_sql.append(str(compiled))
        return []

    Query.all = compile_with_postgres
    engine = create_engine("sqlite://")
    try:
        with Session(engine) as session:
            results = get_notes_for_osis(session, osis="John.1.1", tag="Prologue")
            assert results == []
    finally:
        Query.all = original_all
        engine.dispose()

    assert compiled_sql, "Expected SQL to be compiled against Postgres dialect"
    assert "lower(cast(" in compiled_sql[0].lower()
