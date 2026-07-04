import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_fanout import HOOK_URL, create_sub, post_event, tick


def deliver_one(client: TestClient, db_session: Session, status: int = 200) -> tuple[str, str]:
    """Create sub + matching event and run one tick; returns (event_id, subscription_id)."""
    sub_id = create_sub(client)
    event_id = post_event(client)
    with respx.mock:
        respx.post(HOOK_URL).mock(return_value=httpx.Response(status))
        tick(db_session)
    return event_id, sub_id


class TestDeliveryQueries:
    def test_query_by_event_id(self, client: TestClient, db_session: Session) -> None:
        event_id, sub_id = deliver_one(client, db_session)

        rows = client.get("/api/v1/deliveries", params={"event_id": event_id}).json()
        assert len(rows) == 1
        assert rows[0]["event_id"] == event_id
        assert rows[0]["subscription_id"] == sub_id
        assert rows[0]["state"] == "delivered"
        assert rows[0]["attempt_count"] == 1

    def test_query_by_subscription_id(self, client: TestClient, db_session: Session) -> None:
        event_id, sub_id = deliver_one(client, db_session)
        post_event(client, id="evt-2")  # second matching event, still pending

        rows = client.get("/api/v1/deliveries", params={"subscription_id": sub_id}).json()
        assert [(r["event_id"], r["state"]) for r in rows] == [
            (event_id, "delivered"),
            ("evt-2", "pending"),
        ]

    def test_query_without_filters_is_rejected(self, client: TestClient) -> None:
        response = client.get("/api/v1/deliveries")
        assert response.status_code == 422

    def test_unknown_ids_return_empty_list(self, client: TestClient) -> None:
        assert client.get("/api/v1/deliveries", params={"event_id": "nope"}).json() == []


class TestDeliveryAudit:
    def test_attempt_history_for_delivery(self, client: TestClient, db_session: Session) -> None:
        event_id, _ = deliver_one(client, db_session, status=200)
        delivery_id = client.get(
            "/api/v1/deliveries", params={"event_id": event_id}
        ).json()[0]["id"]

        audit = client.get(f"/api/v1/deliveries/{delivery_id}/attempts").json()
        assert audit["delivery"]["state"] == "delivered"
        assert len(audit["attempts"]) == 1
        attempt = audit["attempts"][0]
        assert attempt["http_status"] == 200
        assert attempt["error"] is None
        assert attempt["attempted_at"]

    def test_unknown_delivery_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/deliveries/nope/attempts")
        assert response.status_code == 404
        assert response.json() == {"detail": "delivery not found"}
