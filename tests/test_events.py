from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Delivery, Event

VALID_BODY: dict[str, Any] = {
    "id": "evt-001",
    "type": "order.created",
    "source": "checkout",
    "payload": {"order_id": 42, "amount": 199.5},
}


def post_event(client: TestClient, body: dict[str, Any]) -> Any:
    return client.post("/api/v1/events", json=body)


class TestIngestionHappyPath:
    def test_accepts_and_persists_event(self, client: TestClient, db_session: Session) -> None:
        response = post_event(client, VALID_BODY)

        assert response.status_code == 202
        assert response.json() == {"event_id": "evt-001", "duplicate": False}

        stored = db_session.get(Event, "evt-001")
        assert stored is not None
        assert stored.type == "order.created"
        assert stored.source == "checkout"
        assert stored.payload == VALID_BODY["payload"]

    def test_generates_id_when_client_omits_it(
        self, client: TestClient, db_session: Session
    ) -> None:
        body = {k: v for k, v in VALID_BODY.items() if k != "id"}
        response = post_event(client, body)

        assert response.status_code == 202
        event_id = response.json()["event_id"]
        assert len(event_id) == 32  # server-generated uuid4 hex
        assert db_session.get(Event, event_id) is not None

    def test_no_deliveries_enqueued_without_subscriptions(
        self, client: TestClient, db_session: Session
    ) -> None:
        post_event(client, VALID_BODY)
        assert db_session.scalars(select(Delivery)).all() == []


class TestIngestionIdempotency:
    def test_replay_returns_202_with_duplicate_flag(
        self, client: TestClient, db_session: Session
    ) -> None:
        first = post_event(client, VALID_BODY)
        replay = post_event(client, VALID_BODY)

        assert first.json() == {"event_id": "evt-001", "duplicate": False}
        assert replay.status_code == 202
        assert replay.json() == {"event_id": "evt-001", "duplicate": True}
        assert len(db_session.scalars(select(Event)).all()) == 1

    def test_replay_with_different_body_keeps_original(
        self, client: TestClient, db_session: Session
    ) -> None:
        post_event(client, VALID_BODY)
        conflicting = {**VALID_BODY, "payload": {"tampered": True}}
        response = post_event(client, conflicting)

        assert response.status_code == 202
        assert response.json()["duplicate"] is True
        stored = db_session.get(Event, "evt-001")
        assert stored is not None
        assert stored.payload == VALID_BODY["payload"]


class TestIngestionValidation:
    @pytest.mark.parametrize(
        ("mutation", "reason"),
        [
            ({"type": None}, "missing type"),
            ({"source": None}, "missing source"),
            ({"payload": None}, "missing payload"),
            ({"type": ""}, "blank type"),
            ({"source": ""}, "blank source"),
            ({"id": ""}, "blank id"),
            ({"id": "x" * 129}, "id too long"),
            ({"type": "x" * 257}, "type too long"),
            ({"payload": [1, 2, 3]}, "payload must be a JSON object"),
            ({"payload": "not-a-dict"}, "payload must be a JSON object"),
            ({"unexpected": "field"}, "unknown fields rejected"),
        ],
    )
    def test_invalid_bodies_get_422(
        self, client: TestClient, mutation: dict[str, Any], reason: str
    ) -> None:
        body = {**VALID_BODY, **mutation}
        body = {k: v for k, v in body.items() if v is not None}
        response = post_event(client, body)
        assert response.status_code == 422, reason
        assert "detail" in response.json()

    def test_non_json_body_gets_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/events", content=b"not json", headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


class TestIngestionFailures:
    def test_unhandled_error_returns_clean_500(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def explode(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("secret internal detail")

        monkeypatch.setattr("app.api.events.ingest_event", explode)
        response = post_event(client, VALID_BODY)

        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
        assert "secret internal detail" not in response.text
        assert "RuntimeError" not in response.text
        assert response.headers["X-Request-ID"]
