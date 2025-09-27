from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from theo.services.api.app.core.database import get_engine
from theo.services.api.app.db.models import Document
from theo.services.api.app.main import app


def test_watchlist_crud_and_alert_flow() -> None:
    with TestClient(app) as client:
        create_response = client.post(
            "/ai/digest/watchlists",
            json={
                "user_id": "watcher-1",
                "name": "Christology topics",
                "filters": {"topics": ["Christology"]},
                "cadence": "daily",
                "delivery_channels": ["in_app"],
            },
        )
        assert create_response.status_code == 201, create_response.text
        watchlist_id = create_response.json()["id"]

        engine = get_engine()
        with Session(engine) as session:
            document = Document(
                title="Exploring Christology",
                source_type="test",
                topics=["Christology"],
                abstract="A study into the Logos and hope.",
            )
            session.add(document)
            session.commit()

        preview = client.get(f"/ai/digest/watchlists/{watchlist_id}/preview")
        assert preview.status_code == 200, preview.text
        preview_payload = preview.json()
        assert preview_payload["delivery_status"] == "preview"
        assert preview_payload["matches"], preview_payload

        events_initial = client.get(f"/ai/digest/watchlists/{watchlist_id}/events")
        assert events_initial.status_code == 200
        assert events_initial.json() == []

        run_response = client.post(f"/ai/digest/watchlists/{watchlist_id}/run")
        assert run_response.status_code == 200, run_response.text
        run_payload = run_response.json()
        assert run_payload["id"]
        assert run_payload["matches"], run_payload
        assert run_payload["document_ids"], run_payload

        events_after = client.get(f"/ai/digest/watchlists/{watchlist_id}/events")
        assert events_after.status_code == 200
        events_payload = events_after.json()
        assert len(events_payload) == 1
        assert events_payload[0]["document_ids"] == run_payload["document_ids"]

        update = client.patch(
            f"/ai/digest/watchlists/{watchlist_id}",
            json={"name": "Updated Christology"},
        )
        assert update.status_code == 200
        assert update.json()["name"] == "Updated Christology"

        delete_response = client.delete(f"/ai/digest/watchlists/{watchlist_id}")
        assert delete_response.status_code == 204

        list_response = client.get(
            "/ai/digest/watchlists", params={"user_id": "watcher-1"}
        )
        assert list_response.status_code == 200
        assert list_response.json() == []
